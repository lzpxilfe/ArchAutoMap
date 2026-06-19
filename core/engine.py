from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsExpression,
    QgsFeature,
    QgsFeatureRequest,
    QgsFields,
    QgsFillSymbol,
    QgsGeometry,
    QgsLayoutExporter,
    QgsLayoutItemMap,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsUnitTypes,
    QgsVectorLayer,
)

from .constants import (
    AUTO_LAYOUT_NAME,
    AUTO_MAP_ITEM_ID,
    MAX_FEATURE_SEARCH_RESULTS,
    MEMORY_LAYER_PROVIDER,
    MIN_FEATURE_SEARCH_CHARS,
    MULTI_POLYGON_GEOMETRY_NAME,
    OUTPUT_MODE_PAIRED,
    POLYGON_GEOMETRY_NAME,
    PREVIEW_TEMP_FILE_PREFIX,
    SYMBOL_SIZE_UNIT_MM,
    TEMP_BEFORE_LAYER_PREFIX,
    TEMP_FILL_LAYER_PREFIX,
    TEMP_OUTLINE_LAYER_PREFIX,
    TRANSPARENT_FILL_COLOR,
)
from .logic import (
    adjusted_scale_from_bbox,
    circle_ratio,
    occupancy_ratios,
    occupancy_status,
    resolve_fill_color,
    sanitize_filename,
    unique_output_path,
)
from .models import (
    BeforeLayerConfig,
    ExportConfig,
    ExportSummary,
    FeatureChoice,
    PreviewMetrics,
)


class ArchAutoMapError(RuntimeError):
    pass


@dataclass
class _PreparedRender:
    layout: QgsPrintLayout
    map_item: QgsLayoutItemMap
    base_layer: object
    overlay_layers: list[QgsVectorLayer]
    name: str
    area_m2: float
    scale: int
    width_ratio: float
    height_ratio: float
    occupancy_ratio: float
    occupancy_label: str
    circle_ratio: float
    temp_layer_ids: list[str]
    original_state: "_MapItemState | None"

    def to_preview_metrics(self, image_path: str) -> PreviewMetrics:
        return PreviewMetrics(
            name=self.name,
            area_m2=self.area_m2,
            scale=self.scale,
            width_ratio=self.width_ratio,
            height_ratio=self.height_ratio,
            occupancy_ratio=self.occupancy_ratio,
            occupancy_label=self.occupancy_label,
            circle_ratio=self.circle_ratio,
            image_path=image_path,
        )


class _MapItemState:
    def __init__(self, map_item: QgsLayoutItemMap):
        self.map_item = map_item
        self.layers = list(map_item.layers() or [])
        self.extent = QgsRectangle(map_item.extent())
        self.crs = map_item.crs()
        self.scale = map_item.scale()
        self.keep_layer_set = (
            map_item.keepLayerSet() if hasattr(map_item, "keepLayerSet") else None
        )
        self.follow_visibility_preset = (
            map_item.followVisibilityPreset()
            if hasattr(map_item, "followVisibilityPreset")
            else None
        )
        self.follow_visibility_preset_name = (
            map_item.followVisibilityPresetName()
            if hasattr(map_item, "followVisibilityPresetName")
            else None
        )

    def restore(self):
        if self.keep_layer_set is not None and hasattr(self.map_item, "setKeepLayerSet"):
            self.map_item.setKeepLayerSet(self.keep_layer_set)
        if self.follow_visibility_preset is not None and hasattr(
            self.map_item, "setFollowVisibilityPreset"
        ):
            self.map_item.setFollowVisibilityPreset(self.follow_visibility_preset)
        if self.follow_visibility_preset_name is not None and hasattr(
            self.map_item, "setFollowVisibilityPresetName"
        ):
            self.map_item.setFollowVisibilityPresetName(self.follow_visibility_preset_name)

        self.map_item.setLayers(self.layers)
        self.map_item.setCrs(self.crs)
        self.map_item.setExtent(self.extent)
        self.map_item.setScale(self.scale)
        self.map_item.refresh()
        if self.map_item.layout():
            self.map_item.layout().refresh()


class ArchAutoMapEngine:
    def __init__(self, project=None, message_callback=None):
        self.project = project or QgsProject.instance()
        self.message_callback = message_callback or (lambda message: None)

    def log(self, message: str):
        self.message_callback(message)

    def list_layout_names(self) -> list[str]:
        return sorted(layout.name() for layout in self.project.layoutManager().printLayouts())

    def list_map_item_ids(self, layout_name: str) -> list[str]:
        layout = self.project.layoutManager().layoutByName(layout_name)
        if layout is None:
            return []

        ids = []
        for item in layout.items():
            if isinstance(item, QgsLayoutItemMap) and item.id():
                ids.append(item.id())
        return sorted(ids)

    def list_feature_choices(
        self,
        fill_layer_id: str,
        name_field: str,
        search_text: str = "",
        max_results: int = MAX_FEATURE_SEARCH_RESULTS,
        minimum_search_chars: int = MIN_FEATURE_SEARCH_CHARS,
    ) -> list[FeatureChoice]:
        layer = self._require_vector_layer(fill_layer_id, "유적 채움")
        if not name_field or layer.fields().indexOf(name_field) < 0:
            return []

        lowered_search = search_text.strip().lower()
        if len(lowered_search) < minimum_search_chars:
            return []

        name_counts: dict[str, int] = {}
        features: list[tuple[int, str]] = []
        request = (
            QgsFeatureRequest()
            .setFilterExpression(self._contains_expression(name_field, lowered_search))
            .setSubsetOfAttributes([name_field], layer.fields())
            .setLimit(max_results)
        )

        for feature in layer.getFeatures(request):
            raw_name = feature[name_field]
            name = str(raw_name).strip() if raw_name not in (None, "") else ""
            if not name:
                continue
            name_counts[name] = name_counts.get(name, 0) + 1
            features.append((feature.id(), name))

        ordered = sorted(features, key=lambda item: (item[1], item[0]))
        return [
            FeatureChoice(
                feature_id=feature_id,
                name=name,
                label=f"{name} [fid:{feature_id}]" if name_counts[name] > 1 else name,
            )
            for feature_id, name in ordered
        ]

    def preview_feature(self, config: ExportConfig, feature_id: int) -> PreviewMetrics:
        feature = self._get_fill_feature(config, feature_id)
        outline_lookup = self._build_outline_lookup(
            config,
            feature_name=self._feature_name(feature, config.name_field),
            max_matches=2,
        )
        prepared = self._prepare_render(config, feature, outline_lookup)

        image_file = tempfile.NamedTemporaryFile(
            prefix=PREVIEW_TEMP_FILE_PREFIX,
            suffix=".jpg",
            delete=False,
        )
        image_path = image_file.name
        image_file.close()

        try:
            self._render_with_overlay(prepared)
            self._export_layout_image(prepared.layout, image_path, config.preview_dpi)
            return prepared.to_preview_metrics(image_path)
        finally:
            self._cleanup_render(prepared)

    def export_current(self, config: ExportConfig, feature_id: int) -> list[str]:
        feature = self._get_fill_feature(config, feature_id)
        outline_lookup = self._build_outline_lookup(
            config,
            feature_name=self._feature_name(feature, config.name_field),
            max_matches=2,
        )
        return self._export_feature(config, feature, outline_lookup, set())

    def export_all(self, config: ExportConfig, progress_callback=None) -> ExportSummary:
        fill_layer = self._require_vector_layer(config.fill_layer_id, "유적 채움")
        features = self._list_named_features(fill_layer, config.name_field)

        # 외곽선 lookup 구성 실패 시 graceful fallback
        try:
            outline_lookup = self._build_outline_lookup(config)
        except Exception as exc:  # pylint: disable=broad-except
            self.log(f"외곽선 lookup 구성 실패 (외곽선 없이 진행): {exc}")
            outline_lookup = None

        os.makedirs(config.output_dir, exist_ok=True)
        total = len(features)
        exported = 0
        failed = 0
        used_paths: set[str] = set()

        for index, feature in enumerate(features, start=1):
            # _feature_name도 try-except 안에 포함해 개별 오류가 전체를 중단시키지 않도록
            try:
                name = self._feature_name(feature, config.name_field) or f"feature_{index}"
                if progress_callback is not None:
                    progress_callback(index, total, name)
                self.log(f"[{index}/{total}] 출력 중: {name}")
                self._export_feature(config, feature, outline_lookup, used_paths)
                exported += 1
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                self.log(f"[{index}/{total}] 실패: feature_{index} ({exc})")

        return ExportSummary(
            total=total,
            exported=exported,
            failed=failed,
            output_dir=config.output_dir,
        )

    def _export_feature(
        self,
        config: ExportConfig,
        feature: QgsFeature,
        outline_lookup: dict[str, list[QgsFeature]] | None,
        used_paths: set[str],
    ) -> list[str]:
        if not config.output_dir:
            raise ArchAutoMapError("출력 폴더가 필요합니다.")

        os.makedirs(config.output_dir, exist_ok=True)
        prepared = self._prepare_render(config, feature, outline_lookup)
        output_paths: list[str] = []
        try:
            stem = sanitize_filename(prepared.name)
            if config.output_mode == OUTPUT_MODE_PAIRED:
                before_path = unique_output_path(config.output_dir, f"{stem}-1", ".jpg", used_paths)
                after_path = unique_output_path(
                    config.output_dir,
                    f"{stem}-2",
                    ".jpg",
                    used_paths,
                )
                # Before 도면: before 레이어가 있으면 이름 매칭으로 이전 경계 표시,
                # 없으면 기존처럼 배경만 출력
                before_temp_ids = self._render_before(
                    prepared=prepared,
                    config=config,
                    feature_name=prepared.name,
                    output_crs=self._resolve_output_crs(config.output_crs_authid),
                )
                self._export_layout_image(prepared.layout, before_path, config.dpi)
                output_paths.append(before_path)
                # 임시 before 레이어 정리
                for bid in before_temp_ids:
                    if self.project.mapLayer(bid) is not None:
                        self.project.removeMapLayer(bid)

                # After 도면: 기존 overlay 렌더링
                self._render_with_overlay(prepared)
                self._export_layout_image(prepared.layout, after_path, config.dpi)
                output_paths.append(after_path)
            else:
                final_path = unique_output_path(config.output_dir, stem, ".jpg", used_paths)
                self._render_with_overlay(prepared)
                self._export_layout_image(prepared.layout, final_path, config.dpi)
                output_paths.append(final_path)
        finally:
            self._cleanup_render(prepared)

        return output_paths

    def _prepare_render(
        self,
        config: ExportConfig,
        feature: QgsFeature,
        outline_lookup: dict[str, list[QgsFeature]] | None,
    ) -> _PreparedRender:
        base_layer = self._require_layer(config.base_layer_id, "배경")
        fill_layer = self._require_vector_layer(config.fill_layer_id, "유적 채움")
        outline_layer = (
            self._require_vector_layer(config.outline_layer_id, "유적 외곽선")
            if config.outline_layer_id
            else None
        )
        output_crs = self._resolve_output_crs(config.output_crs_authid)
        layout, map_item, original_state = self._resolve_layout_target(config)

        raw_name = self._feature_name(feature, config.name_field)
        fill_geometry = self._transform_geometry(feature.geometry(), fill_layer.crs(), output_crs)
        if fill_geometry.isEmpty():
            raise ArchAutoMapError(f"빈 geometry입니다: {raw_name}")

        area_m2 = self._resolve_area(config, feature, fill_geometry, fill_layer)
        bbox = fill_geometry.boundingBox()
        if bbox.width() <= 0 or bbox.height() <= 0:
            raise ArchAutoMapError(f"유효하지 않은 bbox입니다: {raw_name}")

        map_width_mm, map_height_mm = self._map_item_size_mm(map_item)
        final_scale = adjusted_scale_from_bbox(
            feature_width_m=bbox.width(),
            feature_height_m=bbox.height(),
            map_width_mm=map_width_mm,
            map_height_mm=map_height_mm,
            target_ratio=config.target_occupancy_ratio,
            use_standard_scales=config.use_standard_scales,
            min_context_buffer_m=config.min_context_buffer_m,
        )
        width_ratio, height_ratio = occupancy_ratios(
            feature_width_m=bbox.width(),
            feature_height_m=bbox.height(),
            scale=final_scale,
            map_width_mm=map_width_mm,
            map_height_mm=map_height_mm,
        )
        occupancy_ratio = max(width_ratio, height_ratio)
        occupancy_label = occupancy_status(occupancy_ratio)
        extent = self._extent_from_bbox_center(bbox, final_scale, map_width_mm, map_height_mm)
        fill_color_hex = self._resolve_fill_color(config, feature)

        temp_layers = [
            self._create_temp_fill_layer(
                source_layer=fill_layer,
                source_feature=feature,
                geometry=fill_geometry,
                output_crs=output_crs,
                name=raw_name,
                config=config,
                fill_color_hex=fill_color_hex,
                include_outline=outline_layer is None,
            )
        ]
        if outline_layer is not None:
            outline_feature, outline_geometry = self._resolve_outline_feature(
                outline_layer,
                output_crs,
                raw_name,
                fill_geometry,
                outline_lookup,
            )
            temp_layers.append(
                self._create_temp_outline_layer(
                    source_layer=outline_layer if outline_feature is not None else fill_layer,
                    source_feature=outline_feature if outline_feature is not None else feature,
                    geometry=outline_geometry,
                    output_crs=output_crs,
                    name=raw_name,
                    config=config,
                    # style.enabled 이면 설정 스타일 적용.
                    # 외곽선 피처 미발견 시에도 fill geometry를 폴리곤으로 그리지 않도록
                    # style override(투명 채움 + 외곽선만)를 강제한다.
                    use_style_override=(config.style.enabled or outline_feature is None),
                )
            )

        temp_layer_ids = []
        for layer in temp_layers:
            self.project.addMapLayer(layer, False)
            temp_layer_ids.append(layer.id())

        self._configure_map_item(
            map_item=map_item,
            layout=layout,
            output_crs=output_crs,
            extent=extent,
            scale=final_scale,
            base_layer=base_layer,
            overlay_layers=temp_layers,
        )

        return _PreparedRender(
            layout=layout,
            map_item=map_item,
            base_layer=base_layer,
            overlay_layers=temp_layers,
            name=raw_name,
            area_m2=area_m2,
            scale=final_scale,
            width_ratio=width_ratio,
            height_ratio=height_ratio,
            occupancy_ratio=occupancy_ratio,
            occupancy_label=occupancy_label,
            circle_ratio=circle_ratio(width_ratio, height_ratio),
            temp_layer_ids=temp_layer_ids,
            original_state=original_state,
        )

    def _render_base_only(self, prepared: _PreparedRender):
        prepared.map_item.setLayers([prepared.base_layer])
        prepared.map_item.refresh()
        prepared.layout.refresh()

    def _render_with_overlay(self, prepared: _PreparedRender):
        layers = list(reversed(prepared.overlay_layers)) + [prepared.base_layer]
        prepared.map_item.setLayers(layers)
        prepared.map_item.refresh()
        prepared.layout.refresh()

    def _render_before(
        self,
        prepared: _PreparedRender,
        config: ExportConfig,
        feature_name: str,
        output_crs: QgsCoordinateReferenceSystem,
    ) -> list[str]:
        """Before 도면을 렌더링한다.

        before_layer_configs에 레이어가 있으면 이름 매칭으로 이전 경계를
        외곽선 스타일로 오버레이하고, 없으면 배경만 표시한다.
        반환값: 이번에 추가한 임시 before 레이어 ID 목록
        """
        before_temp_layers: list[QgsVectorLayer] = []

        for before_cfg in config.before_layer_configs:
            layer = self._create_temp_before_layer(
                before_cfg=before_cfg,
                feature_name=feature_name,
                output_crs=output_crs,
                config=config,
            )
            if layer is not None:
                self.project.addMapLayer(layer, False)
                before_temp_layers.append(layer)

        if before_temp_layers:
            # 순서: 위에서부터 최신 before → 오래된 before → base
            layers = list(reversed(before_temp_layers)) + [prepared.base_layer]
        else:
            layers = [prepared.base_layer]

        prepared.map_item.setLayers(layers)
        prepared.map_item.refresh()
        prepared.layout.refresh()

        return [layer.id() for layer in before_temp_layers]

    def _create_temp_before_layer(
        self,
        before_cfg: BeforeLayerConfig,
        feature_name: str,
        output_crs: QgsCoordinateReferenceSystem,
        config: ExportConfig,
    ) -> "QgsVectorLayer | None":
        """Before 레이어에서 이름이 일치하는 피처를 찾아 임시 외곽선 레이어를 반환한다.

        매칭 실패(0건 or 2건 이상) 시 None을 반환하고 로그만 남긴다.
        """
        try:
            before_layer = self._require_vector_layer(before_cfg.layer_id, "이전 시기 레이어")
        except ArchAutoMapError as exc:
            self.log(f"[Before] 레이어 로드 실패: {exc}")
            return None

        if before_layer.fields().indexOf(before_cfg.name_field) < 0:
            self.log(
                f"[Before] '{before_layer.name()}'에 이름 필드 '{before_cfg.name_field}'가 없습니다. 건너뜁니다."
            )
            return None

        # 이름 기반 매칭
        request = QgsFeatureRequest().setFilterExpression(
            QgsExpression.createFieldEqualityExpression(before_cfg.name_field, feature_name)
        )
        matched = []
        fields = before_layer.fields()
        for feat in before_layer.getFeatures(request):
            safe = QgsFeature(fields)
            safe.setGeometry(feat.geometry())
            attrs = feat.attributes()
            if len(attrs) >= fields.count():
                safe.setAttributes(attrs[:fields.count()])
            else:
                safe.setAttributes(attrs + [None] * (fields.count() - len(attrs)))
            matched.append(safe)

        if len(matched) == 0:
            self.log(f"[Before] '{feature_name}' — '{before_layer.name()}'에서 매칭 피처 없음. 건너뜁니다.")
            return None
        if len(matched) > 1:
            self.log(
                f"[Before] '{feature_name}' — '{before_layer.name()}'에서 {len(matched)}개 중복 매칭. 첫 번째만 사용합니다."
            )

        source_feature = matched[0]
        geometry = self._transform_geometry(source_feature.geometry(), before_layer.crs(), output_crs)
        if geometry.isEmpty():
            self.log(f"[Before] '{feature_name}' geometry가 비어 있습니다. 건너뜁니다.")
            return None

        # 외곽선만 그리는 임시 레이어 생성
        layer = self._create_temp_feature_layer(
            source_layer=before_layer,
            source_feature=source_feature,
            geometry=geometry,
            output_crs=output_crs,
            name=f"{TEMP_BEFORE_LAYER_PREFIX}{feature_name}",
        )
        # 스타일: 투명 채움 + 외곽선 (after의 outline 스타일 그대로)
        layer.renderer().setSymbol(
            QgsFillSymbol.createSimple(
                {
                    "color": TRANSPARENT_FILL_COLOR,
                    "outline_color": config.style.outline_color_hex,
                    "outline_width": str(config.style.outline_width_mm),
                    "outline_width_unit": SYMBOL_SIZE_UNIT_MM,
                }
            )
        )
        return layer

    def _cleanup_render(self, prepared: _PreparedRender):
        for layer_id in prepared.temp_layer_ids:
            if self.project.mapLayer(layer_id) is not None:
                self.project.removeMapLayer(layer_id)
        if prepared.original_state is not None:
            prepared.original_state.restore()

    def _build_outline_lookup(
        self,
        config: ExportConfig,
        feature_name: str | None = None,
        max_matches: int | None = None,
    ) -> dict[str, list[QgsFeature]] | None:
        if not config.outline_layer_id:
            return None

        outline_layer = self._require_vector_layer(config.outline_layer_id, "유적 외곽선")
        if outline_layer.fields().indexOf(config.name_field) < 0:
            self.log("외곽선 레이어에 유적명 필드가 없어 채움 geometry를 외곽선으로 재사용합니다.")
            return None

        lookup: dict[str, list[QgsFeature]] = {}
        request = QgsFeatureRequest()
        if feature_name:
            request.setFilterExpression(
                QgsExpression.createFieldEqualityExpression(config.name_field, feature_name)
            )
        else:
            request.setSubsetOfAttributes(
                [config.name_field],
                outline_layer.fields(),
            )
        if max_matches:
            request.setLimit(max_matches)

        outline_fields = outline_layer.fields()
        for feature in outline_layer.getFeatures(request):
            # 서자명 키 접근 보장: fields를 명시한 safe copy
            try:
                raw_name = feature[config.name_field]
            except Exception:  # pylint: disable=broad-except
                idx = outline_fields.indexOf(config.name_field)
                attrs = feature.attributes()
                raw_name = attrs[idx] if 0 <= idx < len(attrs) else None
            name = str(raw_name).strip() if raw_name not in (None, "") else ""
            if not name:
                continue
            safe = QgsFeature(outline_fields)
            safe.setGeometry(feature.geometry())
            attrs = feature.attributes()
            if len(attrs) >= outline_fields.count():
                safe.setAttributes(attrs[:outline_fields.count()])
            else:
                safe.setAttributes(attrs + [None] * (outline_fields.count() - len(attrs)))
            lookup.setdefault(name, []).append(safe)
        return lookup

    def _contains_expression(self, field_name: str, lowered_search: str) -> str:
        escaped_field = field_name.replace('"', '""')
        escaped_value = lowered_search.replace("'", "''")
        return f"lower(\"{escaped_field}\") LIKE '%{escaped_value}%'"

    def _resolve_fill_color(self, config: ExportConfig, source_feature: QgsFeature) -> str:
        if not config.style.enabled:
            return config.style.fill_color_hex

        if not config.style.attribute_field or not config.style.attribute_color_rules:
            return config.style.fill_color_hex

        if config.style.attribute_field not in source_feature.fields().names():
            self.log(
                f"표현 기준 필드가 현재 유적에 없어 기본 채움색을 사용합니다: {config.style.attribute_field}"
            )
            return config.style.fill_color_hex

        attribute_value = source_feature[config.style.attribute_field]
        rules = tuple(
            (rule.value, rule.fill_color_hex) for rule in config.style.attribute_color_rules
        )
        return resolve_fill_color(config.style.fill_color_hex, attribute_value, rules)

    def _resolve_outline_feature(
        self,
        outline_layer: QgsVectorLayer,
        output_crs: QgsCoordinateReferenceSystem,
        name: str,
        fallback_geometry: QgsGeometry,
        outline_lookup: dict[str, list[QgsFeature]] | None,
    ) -> tuple[QgsFeature | None, QgsGeometry]:
        if outline_lookup is None:
            return None, QgsGeometry(fallback_geometry)

        matches = outline_lookup.get(name, [])
        if len(matches) != 1:
            if len(matches) > 1:
                self.log(f"외곽선 '{name}' 이(가) 중복되어 채움 geometry를 재사용합니다.")
            else:
                self.log(f"외곽선 '{name}' 을(를) 찾지 못해 채움 geometry를 재사용합니다.")
            return None, QgsGeometry(fallback_geometry)

        outline_feature = matches[0]
        geometry = self._transform_geometry(outline_feature.geometry(), outline_layer.crs(), output_crs)
        if geometry.isEmpty():
            self.log(f"외곽선 '{name}' geometry가 비어 있어 채움 geometry를 재사용합니다.")
            return None, QgsGeometry(fallback_geometry)
        # fields를 명시한 safe copy
        fields = outline_layer.fields()
        safe = QgsFeature(fields)
        safe.setGeometry(outline_feature.geometry())
        attrs = outline_feature.attributes()
        if len(attrs) >= fields.count():
            safe.setAttributes(attrs[:fields.count()])
        else:
            safe.setAttributes(attrs + [None] * (fields.count() - len(attrs)))
        return safe, geometry

    def _list_named_features(self, fill_layer: QgsVectorLayer, name_field: str) -> list[QgsFeature]:
        if fill_layer.fields().indexOf(name_field) < 0:
            raise ArchAutoMapError("유적명 필드가 유적 채움 레이어에 없습니다.")

        fields = fill_layer.fields()
        features = []
        for feature in fill_layer.getFeatures():
            if self._feature_name(feature, name_field):
                # fields를 명시적으로 지정해 복사해야 문자열 키 접근이 보장됨
                copied = QgsFeature(fields)
                copied.setGeometry(feature.geometry())
                copied.setAttributes(feature.attributes())
                features.append(copied)
        return sorted(features, key=lambda item: (self._feature_name(item, name_field), item.id()))

    def _get_fill_feature(self, config: ExportConfig, feature_id: int) -> QgsFeature:
        fill_layer = self._require_vector_layer(config.fill_layer_id, "유적 채움")
        feature = next(fill_layer.getFeatures(QgsFeatureRequest().setFilterFid(feature_id)), None)
        if feature is None:
            raise ArchAutoMapError(f"선택한 유적을 찾을 수 없습니다. fid={feature_id}")
        # fields를 명시적으로 지정해 복사해야 문자열 키 접근이 보장됨
        fields = fill_layer.fields()
        copied = QgsFeature(fields)
        copied.setGeometry(feature.geometry())
        copied.setAttributes(feature.attributes())
        return copied

    def _feature_name(self, feature: QgsFeature, name_field: str) -> str:
        raw_name = feature[name_field] if name_field in feature.fields().names() else None
        return str(raw_name).strip() if raw_name not in (None, "") else ""

    def _resolve_area(
        self,
        config: ExportConfig,
        feature: QgsFeature,
        geometry: QgsGeometry,
        fill_layer: QgsVectorLayer,
    ) -> float:
        if config.area_field and fill_layer.fields().indexOf(config.area_field) >= 0:
            raw_area = feature[config.area_field]
            if raw_area not in (None, ""):
                try:
                    return float(raw_area)
                except (TypeError, ValueError):
                    self.log(f"면적 필드 값을 해석하지 못해 geometry 면적으로 계산합니다: {raw_area}")
        return float(geometry.area())

    def _resolve_output_crs(self, auth_id: str) -> QgsCoordinateReferenceSystem:
        crs = QgsCoordinateReferenceSystem(auth_id)
        if not crs.isValid():
            raise ArchAutoMapError(f"유효하지 않은 CRS입니다: {auth_id}")
        if crs.isGeographic():
            raise ArchAutoMapError("출력 CRS는 미터 기반 투영좌표계를 사용해야 합니다.")
        return crs

    def _resolve_layout_target(self, config: ExportConfig):
        if config.layout.mode == "existing":
            layout = self.project.layoutManager().layoutByName(config.layout.layout_name)
            if layout is None:
                raise ArchAutoMapError(f"Layout을 찾을 수 없습니다: {config.layout.layout_name}")

            map_item = layout.itemById(config.layout.map_item_id)
            if not isinstance(map_item, QgsLayoutItemMap):
                raise ArchAutoMapError(
                    f"지도 아이템을 찾을 수 없습니다: {config.layout.map_item_id}"
                )
            return layout, map_item, _MapItemState(map_item)

        layout = QgsPrintLayout(self.project)
        layout.initializeDefaults()
        layout.setName(AUTO_LAYOUT_NAME)
        layout.setUnits(QgsUnitTypes.LayoutUnit.LayoutMillimeters)

        page = layout.pageCollection().page(0)
        page.setPageSize(
            QgsLayoutSize(
                config.layout.page_width_mm,
                config.layout.page_height_mm,
                QgsUnitTypes.LayoutUnit.LayoutMillimeters,
            )
        )

        map_item = QgsLayoutItemMap(layout)
        map_item.setId(AUTO_MAP_ITEM_ID)
        map_item.attemptMove(
            QgsLayoutPoint(0, 0, QgsUnitTypes.LayoutUnit.LayoutMillimeters)
        )
        map_item.attemptResize(
            QgsLayoutSize(
                config.layout.page_width_mm,
                config.layout.page_height_mm,
                QgsUnitTypes.LayoutUnit.LayoutMillimeters,
            )
        )
        layout.addLayoutItem(map_item)
        return layout, map_item, None

    def _map_item_size_mm(self, map_item: QgsLayoutItemMap) -> tuple[float, float]:
        size = map_item.sizeWithUnits()
        return float(size.width()), float(size.height())

    def _extent_from_bbox_center(
        self,
        bbox: QgsRectangle,
        scale: int,
        map_width_mm: float,
        map_height_mm: float,
    ) -> QgsRectangle:
        width_m = (map_width_mm * scale) / 1000.0
        height_m = (map_height_mm * scale) / 1000.0
        center = bbox.center()
        half_width = width_m / 2.0
        half_height = height_m / 2.0
        return QgsRectangle(
            center.x() - half_width,
            center.y() - half_height,
            center.x() + half_width,
            center.y() + half_height,
        )

    def _configure_map_item(
        self,
        map_item: QgsLayoutItemMap,
        layout: QgsPrintLayout,
        output_crs: QgsCoordinateReferenceSystem,
        extent: QgsRectangle,
        scale: int,
        base_layer,
        overlay_layers: list[QgsVectorLayer],
    ):
        if hasattr(map_item, "setFollowVisibilityPreset"):
            map_item.setFollowVisibilityPreset(False)
        if hasattr(map_item, "setKeepLayerSet"):
            map_item.setKeepLayerSet(True)

        # 레이어 순서는 _render_base_only / _render_with_overlay 에서 결정한다.
        # 여기서는 CRS·범위·축척만 설정한다.
        map_item.setCrs(output_crs)
        map_item.setExtent(extent)
        map_item.setScale(scale)
        map_item.refresh()
        layout.refresh()

    def _create_temp_feature_layer(
        self,
        source_layer: QgsVectorLayer,
        source_feature: QgsFeature,
        geometry: QgsGeometry,
        output_crs: QgsCoordinateReferenceSystem,
        name: str,
    ) -> QgsVectorLayer:
        layer = QgsVectorLayer(
            self._memory_polygon_uri(geometry, output_crs.authid()),
            name,
            MEMORY_LAYER_PROVIDER,
        )
        provider = layer.dataProvider()
        provider.addAttributes(list(source_layer.fields()))
        layer.updateFields()

        feature = QgsFeature(layer.fields())
        feature.setAttributes(list(source_feature.attributes()))
        feature.setGeometry(geometry)
        provider.addFeature(feature)
        layer.updateExtents()
        if hasattr(layer, "setOpacity"):
            layer.setOpacity(source_layer.opacity())
        return layer

    def _create_temp_fill_layer(
        self,
        source_layer: QgsVectorLayer,
        source_feature: QgsFeature,
        geometry: QgsGeometry,
        output_crs: QgsCoordinateReferenceSystem,
        name: str,
        config: ExportConfig,
        fill_color_hex: str,
        include_outline: bool,
    ) -> QgsVectorLayer:
        layer = self._create_temp_feature_layer(
            source_layer=source_layer,
            source_feature=source_feature,
            geometry=geometry,
            output_crs=output_crs,
            name=f"{TEMP_FILL_LAYER_PREFIX}{name}",
        )
        if config.style.enabled:
            symbol_props = {
                "color": fill_color_hex,
                "outline_color": config.style.outline_color_hex,
                "outline_width": str(config.style.outline_width_mm),
                "outline_width_unit": SYMBOL_SIZE_UNIT_MM,
            }
            if not include_outline:
                symbol_props["outline_style"] = "no"
            layer.renderer().setSymbol(QgsFillSymbol.createSimple(symbol_props))
        elif source_layer.renderer() is not None:
            layer.setRenderer(source_layer.renderer().clone())
        return layer

    def _create_temp_outline_layer(
        self,
        source_layer: QgsVectorLayer,
        source_feature: QgsFeature,
        geometry: QgsGeometry,
        output_crs: QgsCoordinateReferenceSystem,
        name: str,
        config: ExportConfig,
        use_style_override: bool,
    ) -> QgsVectorLayer:
        layer = self._create_temp_feature_layer(
            source_layer=source_layer,
            source_feature=source_feature,
            geometry=geometry,
            output_crs=output_crs,
            name=f"{TEMP_OUTLINE_LAYER_PREFIX}{name}",
        )
        if use_style_override:
            layer.renderer().setSymbol(
                QgsFillSymbol.createSimple(
                    {
                        "color": TRANSPARENT_FILL_COLOR,
                        "outline_color": config.style.outline_color_hex,
                        "outline_width": str(config.style.outline_width_mm),
                        "outline_width_unit": SYMBOL_SIZE_UNIT_MM,
                    }
                )
            )
        elif source_layer.renderer() is not None:
            layer.setRenderer(source_layer.renderer().clone())
        return layer

    def _transform_geometry(
        self,
        geometry: QgsGeometry,
        source_crs: QgsCoordinateReferenceSystem,
        output_crs: QgsCoordinateReferenceSystem,
    ) -> QgsGeometry:
        new_geometry = QgsGeometry(geometry)
        if source_crs != output_crs:
            transform = QgsCoordinateTransform(
                source_crs,
                output_crs,
                self.project.transformContext(),
            )
            new_geometry.transform(transform)
        return new_geometry

    def _memory_polygon_uri(self, geometry: QgsGeometry, auth_id: str) -> str:
        geometry_name = (
            MULTI_POLYGON_GEOMETRY_NAME
            if geometry.isMultipart()
            else POLYGON_GEOMETRY_NAME
        )
        return f"{geometry_name}?crs={auth_id}"

    def _require_layer(self, layer_id: str, label: str):
        layer = self.project.mapLayer(layer_id)
        if layer is None:
            raise ArchAutoMapError(f"{label} 레이어를 찾을 수 없습니다.")
        return layer

    def _require_vector_layer(self, layer_id: str | None, label: str) -> QgsVectorLayer:
        if not layer_id:
            raise ArchAutoMapError(f"{label} 레이어가 선택되지 않았습니다.")
        layer = self.project.mapLayer(layer_id)
        if layer is None or not isinstance(layer, QgsVectorLayer):
            raise ArchAutoMapError(f"{label} 레이어가 유효한 벡터 레이어가 아닙니다.")
        return layer

    def _export_layout_image(self, layout: QgsPrintLayout, path: str, dpi: int):
        exporter = QgsLayoutExporter(layout)
        settings = QgsLayoutExporter.ImageExportSettings()
        settings.dpi = dpi
        result = exporter.exportToImage(path, settings)
        # QgsLayoutExporter.Success == 0; 파일 존재 여부도 함께 확인한다.
        if result != 0 or not os.path.exists(path):
            raise ArchAutoMapError(f"이미지 내보내기에 실패했습니다: {path}")
