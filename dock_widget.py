from __future__ import annotations

import os

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QPainter, QPen, QPixmap
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QColorDialog,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayerProxyModel, QgsProject
from qgis.gui import QgsMapLayerComboBox

from .core.engine import ArchAutoMapEngine
from .core.logic import AUTO_LAYOUT_HEIGHT_MM, AUTO_LAYOUT_WIDTH_MM
from .core.models import ExportConfig, LayoutConfig, StyleConfig
from .core.settings import PluginSettings


class OccupancyDiagramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ratio = 0.05
        self.setMinimumSize(120, 120)

    def set_ratio(self, ratio: float):
        self._ratio = max(0.05, min(0.98, ratio))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        margin = 10
        size = min(self.width(), self.height()) - (margin * 2)
        square_x = (self.width() - size) / 2
        square_y = (self.height() - size) / 2

        painter.setPen(QPen(QColor("#444444"), 2))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(square_x, square_y, size, size)

        diameter = size * self._ratio
        circle_x = square_x + (size - diameter) / 2
        circle_y = square_y + (size - diameter) / 2

        painter.setPen(QPen(QColor("#b53a22"), 1.5))
        painter.setBrush(QColor("#d64c31"))
        painter.drawEllipse(circle_x, circle_y, diameter, diameter)


class ArchAutoMapDockWidget(QDockWidget):
    closed = pyqtSignal()

    def __init__(self, iface, parent=None):
        super().__init__("ArchAutoMap", parent)
        self.iface = iface
        self.project = QgsProject.instance()
        self.settings = PluginSettings()
        self.engine = ArchAutoMapEngine(message_callback=self.log)
        self._preview_image_path = None
        self._fill_color = QColor("#d64c31")
        self._outline_color = QColor("#1f1f1f")

        self.setObjectName("ArchAutoMapDockWidget")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._build_ui()
        self._connect_signals()
        self._refresh_layouts()
        self._load_state()
        self._refresh_feature_choices()

    def closeEvent(self, event):  # noqa: N802
        self._persist_state()
        self._cleanup_preview_file()
        self.closed.emit()
        super().closeEvent(event)

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget(scroll)
        root = QVBoxLayout(container)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        root.addWidget(self._build_input_group())
        root.addWidget(self._build_style_group())
        root.addWidget(self._build_preview_group())
        root.addWidget(self._build_export_group())
        root.addWidget(self._build_log_group())
        root.addStretch(1)

        scroll.setWidget(container)
        self.setWidget(scroll)

    def _build_input_group(self):
        group = QGroupBox("입력 설정")
        layout = QGridLayout(group)

        self.base_layer_combo = QgsMapLayerComboBox()
        self.fill_layer_combo = QgsMapLayerComboBox()
        self.fill_layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.outline_layer_combo = QgsMapLayerComboBox()
        self.outline_layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.outline_layer_combo.setAllowEmptyLayer(True)
        self.outline_layer_combo.setCurrentIndex(-1)

        self.name_field_combo = QComboBox()
        self.area_field_combo = QComboBox()
        self.output_crs_edit = QLineEdit("EPSG:5186")

        self.layout_mode_combo = QComboBox()
        self.layout_mode_combo.addItem("기존 Layout 사용", "existing")
        self.layout_mode_combo.addItem("자동 Layout 생성", "auto")

        self.layout_name_combo = QComboBox()
        self.map_item_id_combo = QComboBox()
        self.refresh_layouts_button = QPushButton("Layout 새로고침")

        layout.addWidget(QLabel("배경 레이어"), 0, 0)
        layout.addWidget(self.base_layer_combo, 0, 1)
        layout.addWidget(QLabel("유적 채움 레이어"), 1, 0)
        layout.addWidget(self.fill_layer_combo, 1, 1)
        layout.addWidget(QLabel("유적 외곽선 레이어"), 2, 0)
        layout.addWidget(self.outline_layer_combo, 2, 1)
        layout.addWidget(QLabel("유적명 필드"), 3, 0)
        layout.addWidget(self.name_field_combo, 3, 1)
        layout.addWidget(QLabel("면적 필드"), 4, 0)
        layout.addWidget(self.area_field_combo, 4, 1)
        layout.addWidget(QLabel("출력 CRS"), 5, 0)
        layout.addWidget(self.output_crs_edit, 5, 1)
        layout.addWidget(QLabel("Layout 모드"), 6, 0)
        layout.addWidget(self.layout_mode_combo, 6, 1)
        layout.addWidget(QLabel("Layout 이름"), 7, 0)
        layout.addWidget(self.layout_name_combo, 7, 1)
        layout.addWidget(QLabel("Map Item ID"), 8, 0)
        layout.addWidget(self.map_item_id_combo, 8, 1)
        layout.addWidget(self.refresh_layouts_button, 9, 1)

        return group

    def _build_style_group(self):
        group = QGroupBox("표현 설정")
        layout = QFormLayout(group)

        self.fill_color_button = QPushButton()
        self.outline_color_button = QPushButton()
        self.outline_width_spin = QDoubleSpinBox()
        self.outline_width_spin.setRange(0.1, 5.0)
        self.outline_width_spin.setSingleStep(0.1)
        self.outline_width_spin.setValue(0.6)
        self.outline_width_spin.setSuffix(" mm")

        self._apply_button_color(self.fill_color_button, self._fill_color)
        self._apply_button_color(self.outline_color_button, self._outline_color)

        layout.addRow("채움색", self.fill_color_button)
        layout.addRow("외곽선 색", self.outline_color_button)
        layout.addRow("외곽선 두께", self.outline_width_spin)
        return group

    def _build_preview_group(self):
        group = QGroupBox("미리보기")
        layout = QVBoxLayout(group)

        top_row = QHBoxLayout()
        self.feature_search_edit = QLineEdit()
        self.feature_search_edit.setPlaceholderText("유적명 검색")
        self.feature_combo = QComboBox()
        self.preview_button = QPushButton("현재 유적 미리보기")
        top_row.addWidget(self.feature_search_edit)
        top_row.addWidget(self.feature_combo, stretch=1)
        top_row.addWidget(self.preview_button)

        preview_row = QHBoxLayout()
        self.preview_image_label = QLabel("미리보기 이미지")
        self.preview_image_label.setAlignment(Qt.AlignCenter)
        self.preview_image_label.setFrameShape(QFrame.StyledPanel)
        self.preview_image_label.setMinimumSize(300, 220)

        side_panel = QVBoxLayout()
        side_panel.addWidget(QLabel("도면 점유율 도식"))
        self.occupancy_widget = OccupancyDiagramWidget()
        side_panel.addWidget(self.occupancy_widget)

        self.metrics_label = QLabel(
            "가로 점유율: -\n세로 점유율: -\n판정: -\n축척: -\n면적: -"
        )
        self.metrics_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        side_panel.addWidget(self.metrics_label)
        side_panel.addStretch(1)

        preview_row.addWidget(self.preview_image_label, stretch=3)
        preview_row.addLayout(side_panel, stretch=2)

        layout.addLayout(top_row)
        layout.addLayout(preview_row)
        return group

    def _build_export_group(self):
        group = QGroupBox("출력")
        layout = QGridLayout(group)

        self.output_mode_combo = QComboBox()
        self.output_mode_combo.addItem("최종도면 1장", "final_only")
        self.output_mode_combo.addItem("배경도 + 유적도 2장", "paired")

        self.output_dir_edit = QLineEdit()
        self.output_dir_button = QPushButton("폴더 선택")
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)

        self.export_current_button = QPushButton("현재 유적 JPG 출력")
        self.export_all_button = QPushButton("전체 유적 일괄 출력")
        self.progress_label = QLabel("대기 중")

        layout.addWidget(QLabel("출력 방식"), 0, 0)
        layout.addWidget(self.output_mode_combo, 0, 1, 1, 2)
        layout.addWidget(QLabel("출력 폴더"), 1, 0)
        layout.addWidget(self.output_dir_edit, 1, 1)
        layout.addWidget(self.output_dir_button, 1, 2)
        layout.addWidget(QLabel("DPI"), 2, 0)
        layout.addWidget(self.dpi_spin, 2, 1, 1, 2)
        layout.addWidget(self.export_current_button, 3, 1)
        layout.addWidget(self.export_all_button, 3, 2)
        layout.addWidget(self.progress_label, 4, 1, 1, 2)

        return group

    def _build_log_group(self):
        group = QGroupBox("로그")
        layout = QVBoxLayout(group)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(140)
        layout.addWidget(self.log_edit)
        return group

    def _connect_signals(self):
        self.fill_layer_combo.layerChanged.connect(self._on_fill_layer_changed)
        self.outline_layer_combo.layerChanged.connect(self._persist_state)
        self.base_layer_combo.layerChanged.connect(self._persist_state)
        self.name_field_combo.currentIndexChanged.connect(self._on_name_field_changed)
        self.area_field_combo.currentIndexChanged.connect(self._persist_state)
        self.feature_search_edit.textChanged.connect(self._refresh_feature_choices)
        self.preview_button.clicked.connect(self._on_preview_clicked)
        self.output_dir_button.clicked.connect(self._choose_output_dir)
        self.export_current_button.clicked.connect(self._on_export_current_clicked)
        self.export_all_button.clicked.connect(self._on_export_all_clicked)
        self.layout_mode_combo.currentIndexChanged.connect(self._on_layout_mode_changed)
        self.layout_name_combo.currentIndexChanged.connect(self._refresh_map_item_ids)
        self.map_item_id_combo.currentIndexChanged.connect(self._persist_state)
        self.refresh_layouts_button.clicked.connect(self._refresh_layouts)
        self.fill_color_button.clicked.connect(lambda: self._select_color("fill"))
        self.outline_color_button.clicked.connect(lambda: self._select_color("outline"))
        self.output_crs_edit.editingFinished.connect(self._persist_state)
        self.output_mode_combo.currentIndexChanged.connect(self._persist_state)
        self.dpi_spin.valueChanged.connect(self._persist_state)
        self.outline_width_spin.valueChanged.connect(self._persist_state)

    def _on_fill_layer_changed(self):
        self._refresh_fields()
        self._refresh_feature_choices()
        self._persist_state()

    def _on_name_field_changed(self):
        self._refresh_feature_choices()
        self._persist_state()

    def _on_layout_mode_changed(self):
        use_existing = self.layout_mode_combo.currentData() == "existing"
        self.layout_name_combo.setEnabled(use_existing)
        self.map_item_id_combo.setEnabled(use_existing)
        self.refresh_layouts_button.setEnabled(use_existing)
        self._persist_state()

    def _refresh_fields(self):
        layer = self.fill_layer_combo.currentLayer()
        self.name_field_combo.blockSignals(True)
        self.area_field_combo.blockSignals(True)
        self.name_field_combo.clear()
        self.area_field_combo.clear()
        self.area_field_combo.addItem("geometry 직접 계산", "")

        if layer is not None:
            for field in layer.fields():
                self.name_field_combo.addItem(field.name())
                self.area_field_combo.addItem(field.name(), field.name())

        self.name_field_combo.blockSignals(False)
        self.area_field_combo.blockSignals(False)

    def _refresh_feature_choices(self):
        self.feature_combo.blockSignals(True)
        current_feature_id = self.feature_combo.currentData()
        self.feature_combo.clear()

        fill_layer = self.fill_layer_combo.currentLayer()
        name_field = self.name_field_combo.currentText().strip()
        if fill_layer is None or not name_field:
            self.feature_combo.blockSignals(False)
            return

        choices = self.engine.list_feature_choices(
            fill_layer.id(),
            name_field,
            self.feature_search_edit.text(),
        )
        for choice in choices:
            self.feature_combo.addItem(choice.label, choice.feature_id)

        if current_feature_id is not None:
            index = self.feature_combo.findData(current_feature_id)
            if index >= 0:
                self.feature_combo.setCurrentIndex(index)

        self.feature_combo.blockSignals(False)

    def _refresh_layouts(self):
        self.layout_name_combo.blockSignals(True)
        self.layout_name_combo.clear()
        for name in self.engine.list_layout_names():
            self.layout_name_combo.addItem(name)
        self.layout_name_combo.blockSignals(False)
        self._refresh_map_item_ids()

    def _refresh_map_item_ids(self):
        self.map_item_id_combo.blockSignals(True)
        self.map_item_id_combo.clear()
        layout_name = self.layout_name_combo.currentText()
        for item_id in self.engine.list_map_item_ids(layout_name):
            self.map_item_id_combo.addItem(item_id)
        self.map_item_id_combo.blockSignals(False)
        self._persist_state()

    def _choose_output_dir(self):
        current = self.output_dir_edit.text().strip() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "출력 폴더 선택", current)
        if path:
            self.output_dir_edit.setText(path)
            self._persist_state()

    def _select_color(self, target: str):
        current = self._fill_color if target == "fill" else self._outline_color
        color = QColorDialog.getColor(current, self, "색상 선택")
        if not color.isValid():
            return
        if target == "fill":
            self._fill_color = color
            self._apply_button_color(self.fill_color_button, color)
        else:
            self._outline_color = color
            self._apply_button_color(self.outline_color_button, color)
        self._persist_state()

    def _apply_button_color(self, button: QPushButton, color: QColor):
        button.setText(color.name().upper())
        button.setStyleSheet(
            "QPushButton {"
            f"background-color: {color.name()};"
            f"color: {'#ffffff' if color.lightness() < 140 else '#111111'};"
            "border: 1px solid #6b6b6b; padding: 4px 8px;}"
        )

    def _on_preview_clicked(self):
        try:
            config = self._gather_config(require_output_dir=False)
            feature_id = self._current_feature_id()
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self._persist_state()
            preview = self.engine.preview_feature(config, feature_id)
        except Exception as exc:  # pylint: disable=broad-except
            self._show_error("미리보기 실패", exc)
            return
        finally:
            QApplication.restoreOverrideCursor()

        self._cleanup_preview_file()
        self._preview_image_path = preview.image_path
        pixmap = QPixmap(preview.image_path)
        self.preview_image_label.setPixmap(
            pixmap.scaled(
                self.preview_image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        self.occupancy_widget.set_ratio(preview.circle_ratio)
        self.metrics_label.setText(
            "\n".join(
                [
                    f"가로 점유율: {preview.width_ratio * 100:.1f}%",
                    f"세로 점유율: {preview.height_ratio * 100:.1f}%",
                    f"판정: {preview.occupancy_label}",
                    f"축척: 1:{preview.scale:,}",
                    f"면적: {preview.area_m2:,.1f}㎡",
                ]
            )
        )
        self.progress_label.setText(f"미리보기 완료: {preview.name}")
        self.log(f"미리보기 완료: {preview.name}")

    def _on_export_current_clicked(self):
        try:
            config = self._gather_config(require_output_dir=True)
            feature_id = self._current_feature_id()
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.progress_label.setText("현재 유적 출력 중...")
            self._persist_state()
            paths = self.engine.export_current(config, feature_id)
        except Exception as exc:  # pylint: disable=broad-except
            self._show_error("현재 유적 출력 실패", exc)
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.progress_label.setText(f"현재 유적 출력 완료 ({len(paths)}개)")
        for path in paths:
            self.log(f"출력 완료: {path}")

    def _on_export_all_clicked(self):
        try:
            config = self._gather_config(require_output_dir=True)
            self._persist_state()
        except Exception as exc:  # pylint: disable=broad-except
            self._show_error("설정 오류", exc)
            return

        def progress_callback(index: int, total: int, name: str):
            self.progress_label.setText(f"[{index}/{total}] {name}")
            QApplication.processEvents()

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            summary = self.engine.export_all(config, progress_callback=progress_callback)
        except Exception as exc:  # pylint: disable=broad-except
            self._show_error("일괄 출력 실패", exc)
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.progress_label.setText(
            f"일괄 출력 완료: 성공 {summary.exported} / 실패 {summary.failed}"
        )
        self.log(
            f"일괄 출력 완료: 총 {summary.total}, 성공 {summary.exported}, 실패 {summary.failed}, 폴더 {summary.output_dir}"
        )

    def _current_feature_id(self) -> int:
        feature_id = self.feature_combo.currentData()
        if feature_id is None:
            raise ValueError("현재 유적이 선택되지 않았습니다.")
        return int(feature_id)

    def _gather_config(self, require_output_dir: bool) -> ExportConfig:
        base_layer = self.base_layer_combo.currentLayer()
        fill_layer = self.fill_layer_combo.currentLayer()

        if base_layer is None:
            raise ValueError("배경 레이어를 선택하세요.")
        if fill_layer is None:
            raise ValueError("유적 채움 레이어를 선택하세요.")

        name_field = self.name_field_combo.currentText().strip()
        if not name_field:
            raise ValueError("유적명 필드를 선택하세요.")

        area_field = self.area_field_combo.currentData()
        if area_field == "":
            area_field = None

        layout_mode = self.layout_mode_combo.currentData()
        layout_name = self.layout_name_combo.currentText().strip()
        map_item_id = self.map_item_id_combo.currentText().strip()
        if layout_mode == "existing":
            if not layout_name:
                raise ValueError("기존 Layout 이름을 선택하세요.")
            if not map_item_id:
                raise ValueError("Map Item ID를 선택하세요.")

        output_dir = self.output_dir_edit.text().strip()
        if require_output_dir and not output_dir:
            raise ValueError("출력 폴더를 지정하세요.")

        return ExportConfig(
            base_layer_id=base_layer.id(),
            fill_layer_id=fill_layer.id(),
            outline_layer_id=(
                self.outline_layer_combo.currentLayer().id()
                if self.outline_layer_combo.currentLayer() is not None
                else None
            ),
            name_field=name_field,
            area_field=area_field,
            output_crs_authid=self.output_crs_edit.text().strip() or "EPSG:5186",
            style=StyleConfig(
                fill_color_hex=self._fill_color.name(),
                outline_color_hex=self._outline_color.name(),
                outline_width_mm=self.outline_width_spin.value(),
            ),
            layout=LayoutConfig(
                mode=layout_mode,
                layout_name=layout_name,
                map_item_id=map_item_id,
                page_width_mm=AUTO_LAYOUT_WIDTH_MM,
                page_height_mm=AUTO_LAYOUT_HEIGHT_MM,
            ),
            dpi=self.dpi_spin.value(),
            output_mode=self.output_mode_combo.currentData(),
            output_dir=output_dir,
        )

    def _persist_state(self):
        self.settings.set(
            "base_layer_id",
            self.base_layer_combo.currentLayer().id() if self.base_layer_combo.currentLayer() else "",
        )
        self.settings.set(
            "fill_layer_id",
            self.fill_layer_combo.currentLayer().id() if self.fill_layer_combo.currentLayer() else "",
        )
        self.settings.set(
            "outline_layer_id",
            self.outline_layer_combo.currentLayer().id()
            if self.outline_layer_combo.currentLayer()
            else "",
        )
        self.settings.set("name_field", self.name_field_combo.currentText())
        self.settings.set("area_field", self.area_field_combo.currentData() or "")
        self.settings.set("output_crs_authid", self.output_crs_edit.text().strip())
        self.settings.set("layout_mode", self.layout_mode_combo.currentData())
        self.settings.set("layout_name", self.layout_name_combo.currentText())
        self.settings.set("map_item_id", self.map_item_id_combo.currentText())
        self.settings.set("fill_color_hex", self._fill_color.name())
        self.settings.set("outline_color_hex", self._outline_color.name())
        self.settings.set("outline_width_mm", self.outline_width_spin.value())
        self.settings.set("feature_search", self.feature_search_edit.text())
        self.settings.set("output_mode", self.output_mode_combo.currentData())
        self.settings.set("output_dir", self.output_dir_edit.text().strip())
        self.settings.set("dpi", self.dpi_spin.value())

    def _load_state(self):
        self._set_layer_if_present(self.base_layer_combo, self.settings.get("base_layer_id", ""))
        self._set_layer_if_present(self.fill_layer_combo, self.settings.get("fill_layer_id", ""))
        self._set_layer_if_present(
            self.outline_layer_combo,
            self.settings.get("outline_layer_id", ""),
        )

        self.output_crs_edit.setText(self.settings.get("output_crs_authid", "EPSG:5186"))
        self.feature_search_edit.setText(self.settings.get("feature_search", ""))
        self.output_dir_edit.setText(self.settings.get("output_dir", ""))
        self.dpi_spin.setValue(int(self.settings.get("dpi", 300)))
        self.outline_width_spin.setValue(float(self.settings.get("outline_width_mm", 0.6)))

        fill_color_hex = self.settings.get("fill_color_hex", "#d64c31")
        outline_color_hex = self.settings.get("outline_color_hex", "#1f1f1f")
        self._fill_color = QColor(fill_color_hex)
        self._outline_color = QColor(outline_color_hex)
        self._apply_button_color(self.fill_color_button, self._fill_color)
        self._apply_button_color(self.outline_color_button, self._outline_color)

        layout_mode = self.settings.get("layout_mode", "existing")
        layout_index = self.layout_mode_combo.findData(layout_mode)
        if layout_index >= 0:
            self.layout_mode_combo.setCurrentIndex(layout_index)

        layout_name = self.settings.get("layout_name", "")
        if layout_name:
            index = self.layout_name_combo.findText(layout_name)
            if index >= 0:
                self.layout_name_combo.setCurrentIndex(index)

        self._refresh_map_item_ids()
        map_item_id = self.settings.get("map_item_id", "")
        if map_item_id:
            index = self.map_item_id_combo.findText(map_item_id)
            if index >= 0:
                self.map_item_id_combo.setCurrentIndex(index)

        output_mode = self.settings.get("output_mode", "final_only")
        output_mode_index = self.output_mode_combo.findData(output_mode)
        if output_mode_index >= 0:
            self.output_mode_combo.setCurrentIndex(output_mode_index)

        self._on_layout_mode_changed()

        saved_name_field = self.settings.get("name_field", "")
        if saved_name_field:
            index = self.name_field_combo.findText(saved_name_field)
            if index >= 0:
                self.name_field_combo.setCurrentIndex(index)

        saved_area_field = self.settings.get("area_field", "")
        if saved_area_field:
            index = self.area_field_combo.findData(saved_area_field)
            if index >= 0:
                self.area_field_combo.setCurrentIndex(index)

    def _set_layer_if_present(self, combo: QgsMapLayerComboBox, layer_id: str):
        if not layer_id:
            return
        layer = self.project.mapLayer(layer_id)
        if layer is not None:
            combo.setLayer(layer)

    def log(self, message: str):
        self.log_edit.appendPlainText(message)

    def _show_error(self, title: str, error: Exception):
        self.log(f"{title}: {error}")
        QMessageBox.warning(self, title, str(error))

    def _cleanup_preview_file(self):
        if self._preview_image_path and os.path.exists(self._preview_image_path):
            try:
                os.remove(self._preview_image_path)
            except OSError:
                pass
        self._preview_image_path = None
