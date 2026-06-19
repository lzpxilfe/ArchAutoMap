from __future__ import annotations

import os

from qgis.PyQt.QtCore import QTimer, Qt, pyqtSignal
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QColor, QPainter, QPen, QPixmap, QFont, QLinearGradient, QBrush
from qgis.PyQt.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QColorDialog,
    QDialog,
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
    QSizePolicy,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayerProxyModel, QgsProject
from qgis.gui import QgsMapLayerComboBox

from .core.constants import (
    AUTO_LAYOUT_HEIGHT_MM,
    AUTO_LAYOUT_MODE,
    AUTO_LAYOUT_WIDTH_MM,
    ATTRIBUTE_STYLE_NONE_LABEL,
    build_color_button_stylesheet,
    build_dock_stylesheet,
    COLOR_BUTTON_LIGHTNESS_THRESHOLD,
    COLOR_BUTTON_TEXT_DARK,
    COLOR_BUTTON_TEXT_LIGHT,
    COLOR_DIALOG_TITLE,
    DEFAULT_DPI,
    DEFAULT_FILL_COLOR_HEX,
    DEFAULT_MIN_CONTEXT_BUFFER_M,
    DEFAULT_OUTPUT_CRS_AUTHID,
    DEFAULT_OUTLINE_COLOR_HEX,
    DEFAULT_OUTLINE_WIDTH_MM,
    DEFAULT_TARGET_OCCUPANCY_RATIO,
    DOCK_DIMENSIONS,
    DOCK_PALETTE,
    DOCK_WIDGET_OBJECT_NAME,
    EXISTING_LAYOUT_MODE,
    FEATURE_NO_RESULTS_PLACEHOLDER,
    FEATURE_SEARCH_INPUT_PLACEHOLDER,
    FEATURE_SEARCH_PLACEHOLDER,
    FEATURE_SELECT_PLACEHOLDER,
    MAX_CONTEXT_BUFFER_M,
    GEOMETRY_AREA_LABEL,
    MAX_DPI,
    MAX_OUTLINE_WIDTH_MM,
    MIN_DPI,
    MIN_FEATURE_SEARCH_CHARS,
    MIN_OUTLINE_WIDTH_MM,
    OCCUPANCY_DIAGRAM_STYLE,
    OUTLINE_LOCK_TOOLTIP,
    OUTLINE_UNLOCK_TOOLTIP,
    OUTLINE_WIDTH_STEP_MM,
    OUTLINE_WIDTH_SUFFIX,
    OUTPUT_DIRECTORY_DIALOG_TITLE,
    OUTPUT_MODE_FINAL_ONLY,
    OUTPUT_MODE_PAIRED,
    PLUGIN_NAME,
    PLUGIN_VERSION,
    SEARCH_DEBOUNCE_MS,
)
from .core.engine import ArchAutoMapEngine
from .core.models import AttributeColorRule, ExportConfig, LayoutConfig, StyleConfig
from .core.settings import PluginSettings, SettingsKey


class OccupancyDiagramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ratio = OCCUPANCY_DIAGRAM_STYLE.min_ratio
        self._bg = QColor(DOCK_PALETTE.diagram_bg)
        self._frame = QColor(DOCK_PALETTE.diagram_frame)
        self._accent = QColor(DOCK_PALETTE.accent)
        self.setMinimumSize(
            DOCK_DIMENSIONS.occupancy_widget_min_size,
            DOCK_DIMENSIONS.occupancy_widget_min_size,
        )

    def set_ratio(self, ratio: float):
        self._ratio = max(
            OCCUPANCY_DIAGRAM_STYLE.min_ratio,
            min(OCCUPANCY_DIAGRAM_STYLE.max_ratio, ratio),
        )
        self.update()

    def paintEvent(self, event):  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        margin = OCCUPANCY_DIAGRAM_STYLE.margin_px
        size = min(self.width(), self.height()) - (margin * 2)
        square_x = (self.width() - size) / 2
        square_y = (self.height() - size) / 2

        # 배경 사각형
        painter.setPen(QPen(self._frame, OCCUPANCY_DIAGRAM_STYLE.frame_width_px))
        painter.setBrush(self._bg)
        rect = QRectF(square_x, square_y, size, size)
        painter.drawRoundedRect(
            rect,
            OCCUPANCY_DIAGRAM_STYLE.corner_radius_px,
            OCCUPANCY_DIAGRAM_STYLE.corner_radius_px,
        )

        # 원
        diameter = size * self._ratio
        circle_x = square_x + (size - diameter) / 2
        circle_y = square_y + (size - diameter) / 2
        circle_rect = QRectF(circle_x, circle_y, diameter, diameter)

        # 그라데이션 브러시
        gradient = QLinearGradient(circle_x, circle_y, circle_x + diameter, circle_y + diameter)
        gradient.setColorAt(0, self._accent.lighter(130))
        gradient.setColorAt(1, self._accent)
        painter.setPen(QPen(self._accent.darker(140), OCCUPANCY_DIAGRAM_STYLE.accent_outline_width_px))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(circle_rect)


class AttributeRuleRow(QFrame):
    changed = pyqtSignal()
    removed = pyqtSignal(object)

    def __init__(self, value: str = "", fill_color_hex: str = DEFAULT_FILL_COLOR_HEX, parent=None):
        super().__init__(parent)
        self._fill_color = QColor(fill_color_hex)
        self.setObjectName("RuleRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.value_edit = QLineEdit(value)
        self.value_edit.setPlaceholderText("속성값")

        self.color_button = QPushButton()
        self.color_button.setObjectName("ColorButton")
        self.remove_button = QPushButton("✕")
        self.remove_button.setObjectName("NeutralButton")
        self.remove_button.setFixedWidth(32)

        layout.addWidget(self.value_edit, stretch=1)
        layout.addWidget(self.color_button)
        layout.addWidget(self.remove_button)

        self.value_edit.textChanged.connect(self.changed.emit)
        self.color_button.clicked.connect(self._choose_color)
        self.remove_button.clicked.connect(lambda: self.removed.emit(self))

        self._apply_button_color()

    def set_controls_enabled(self, enabled: bool):
        self.value_edit.setEnabled(enabled)
        self.color_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)

    def to_rule(self) -> AttributeColorRule | None:
        value = self.value_edit.text().strip()
        if not value:
            return None
        return AttributeColorRule(value=value, fill_color_hex=self._fill_color.name())

    def _choose_color(self):
        color = QColorDialog.getColor(self._fill_color, self, COLOR_DIALOG_TITLE)
        if not color.isValid():
            return
        self._fill_color = color
        self._apply_button_color()
        self.changed.emit()

    def _apply_button_color(self):
        self.color_button.setText(self._fill_color.name().upper())
        foreground = (
            COLOR_BUTTON_TEXT_DARK
            if self._fill_color.lightness() < COLOR_BUTTON_LIGHTNESS_THRESHOLD
            else COLOR_BUTTON_TEXT_LIGHT
        )
        self.color_button.setStyleSheet(
            build_color_button_stylesheet(
                self._fill_color.name(), foreground, DOCK_PALETTE.color_button_border,
            )
        )



class CollapsibleSection(QWidget):
    """접고 펼칠 수 있는 섹션 위젯.

    isChecked() / setChecked() / toggled 시그널을 통해
    QGroupBox(checkable) 과 동일한 인터페이스를 제공합니다.
    """

    toggled = pyqtSignal(bool)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._checked = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 헤더 토글 버튼 — slim inline 스타일
        self._btn = QPushButton(f"▶  {title}")
        self._btn.setObjectName("CollapsibleHeader")
        self._btn.setCheckable(True)
        self._btn.setChecked(False)
        self._btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._btn.setFixedHeight(22)
        self._btn.toggled.connect(self._on_toggled)

        # 콘텐츠 영역
        self._content_widget = QWidget()
        self._content_widget.setObjectName("CollapsibleContent")
        self._content_layout = QFormLayout(self._content_widget)
        self._content_layout.setContentsMargins(10, 6, 10, 8)
        self._content_layout.setLabelAlignment(Qt.AlignTop)
        self._content_layout.setFormAlignment(Qt.AlignTop)
        self._content_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self._content_layout.setSpacing(5)
        self._content_widget.setVisible(False)

        outer.addWidget(self._btn)
        outer.addWidget(self._content_widget)

    # ── 공개 인터페이스 ───────────────────────────────────────────

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, checked: bool):  # noqa: N802
        if self._btn.isChecked() != checked:
            self._btn.setChecked(checked)

    @property
    def form_layout(self) -> QFormLayout:
        return self._content_layout

    def add_row(self, label, widget):
        """QFormLayout.addRow 래퍼."""
        if isinstance(label, str):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {DOCK_PALETTE.text_soft}; font-size: 11px;")
            self._content_layout.addRow(lbl, widget)
        else:
            self._content_layout.addRow(label, widget)

    def add_full_row(self, widget):
        """라벨 없는 전체 너비 행."""
        self._content_layout.addRow(widget)

    # ── 내부 ─────────────────────────────────────────────────────

    def _on_toggled(self, checked: bool):
        self._checked = checked
        self._content_widget.setVisible(checked)
        self._btn.setText(f"{'▼' if checked else '▶'}  {self._title}")
        self.toggled.emit(checked)


class ArchAutoMapDockWidget(QDockWidget):
    """QGIS DockWidget 래퍼 — 내부적으로 독립 다이얼로그를 포함합니다."""

    closed = pyqtSignal()

    def __init__(self, iface, parent=None):
        super().__init__(PLUGIN_NAME, parent)
        self.iface = iface
        self.project = QgsProject.instance()
        self.settings = PluginSettings()
        self.engine = ArchAutoMapEngine(message_callback=self.log)
        self._preview_image_path = None
        self._preview_pixmap = None
        self._fill_color = QColor(DEFAULT_FILL_COLOR_HEX)
        self._outline_color = QColor(DEFAULT_OUTLINE_COLOR_HEX)
        self._style_rule_rows: list[AttributeRuleRow] = []
        self._is_loading_state = True
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._refresh_feature_choices)

        self.setObjectName(DOCK_WIDGET_OBJECT_NAME)

        # ── 독립 부동 창 설정 ─────────────────────────────────────
        # DockWidgetFloatable 허용 + 기본 상태를 float로 설정
        self.setAllowedAreas(Qt.NoDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )
        self.setFloating(True)  # 처음부터 독립 창으로 띄우기

        self.setMinimumWidth(DOCK_DIMENSIONS.width)
        self.setMinimumHeight(DOCK_DIMENSIONS.min_height)
        self._build_ui()
        self._apply_theme()
        self._connect_signals()
        self._refresh_layouts()
        self._load_state()
        self._search_timer.stop()
        self._is_loading_state = False
        self._sync_style_controls()
        self._set_feature_placeholder(FEATURE_SEARCH_PLACEHOLDER)
        self._update_feature_actions()
        self.resize(DOCK_DIMENSIONS.width, DOCK_DIMENSIONS.initial_height)

    def closeEvent(self, event):  # noqa: N802
        self._persist_state()
        self._cleanup_preview_file()
        self.closed.emit()
        super().closeEvent(event)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._update_preview_pixmap()

    # ──────────────────────────────────────────────────────────────
    #  UI 구성
    # ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget(scroll)
        container.setObjectName("ArchAutoMapRoot")
        root = QVBoxLayout(container)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_header_card())
        root.addWidget(self._build_input_group())
        root.addWidget(self._build_style_group())
        root.addWidget(self._build_preview_group())
        root.addWidget(self._build_export_group())
        root.addWidget(self._build_log_group())
        root.addStretch(1)

        scroll.setWidget(container)
        self.setWidget(scroll)

    def _build_header_card(self):
        card = QFrame()
        card.setObjectName("HeroCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(4)

        # 로고 + 타이틀 한 줄
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        badge = QLabel("🗺")
        badge.setStyleSheet("font-size: 22px;")
        title = QLabel(PLUGIN_NAME)
        title.setObjectName("HeroTitle")

        ver = QLabel(f"v{PLUGIN_VERSION}")
        ver.setStyleSheet(
            f"color: {DOCK_PALETTE.text_soft}; font-size: 10px; "
            f"background: {DOCK_PALETTE.surface}; border-radius: 4px; "
            f"padding: 2px 6px;"
        )
        ver.setAlignment(Qt.AlignVCenter)

        title_row.addWidget(badge)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(ver)

        subtitle = QLabel("유적 폴리곤을 자동으로 중앙 배치하고 JPG 도면으로 단건·일괄 출력합니다.")
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)

        layout.addLayout(title_row)
        layout.addWidget(subtitle)
        return card

    def _build_input_group(self):
        group = QGroupBox("입력 설정")
        layout = QGridLayout(group)
        layout.setSpacing(8)
        layout.setColumnStretch(1, 1)

        # ── 레이어 콤보박스 ────────────────────────────────────────
        self.outline_layer_combo = QgsMapLayerComboBox()
        self.outline_layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.outline_layer_combo.setAllowEmptyLayer(True)
        self.outline_layer_combo.setCurrentIndex(-1)
        self.outline_layer_combo.setEnabled(False)   # 기본적으로 잠김

        self._outline_locked = True
        self.outline_lock_btn = QPushButton("🔒")
        self.outline_lock_btn.setObjectName("NeutralButton")
        self.outline_lock_btn.setFixedWidth(30)
        self.outline_lock_btn.setFixedHeight(28)
        self.outline_lock_btn.setToolTip(OUTLINE_LOCK_TOOLTIP)
        self.outline_lock_btn.clicked.connect(self._toggle_outline_lock)

        self.fill_layer_combo = QgsMapLayerComboBox()
        self.fill_layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.base_layer_combo = QgsMapLayerComboBox()

        self.name_field_combo = QComboBox()
        self.area_field_combo = QComboBox()
        self.output_crs_edit = QLineEdit(DEFAULT_OUTPUT_CRS_AUTHID)

        self.target_occupancy_spin = QSpinBox()
        self.target_occupancy_spin.setRange(10, 95)
        self.target_occupancy_spin.setSingleStep(5)
        self.target_occupancy_spin.setValue(60)
        self.target_occupancy_spin.setSuffix(" %")
        self.target_occupancy_spin.setToolTip(
            "도면 내에서 유적이 차지하는 최대 비율입니다. 값을 낮출수록 주변 지형 맥락이 더 많이 포함됩니다 (기본값: 60%)."
        )

        self.min_context_buffer_spin = QSpinBox()
        self.min_context_buffer_spin.setRange(0, MAX_CONTEXT_BUFFER_M)
        self.min_context_buffer_spin.setSingleStep(50)
        self.min_context_buffer_spin.setValue(DEFAULT_MIN_CONTEXT_BUFFER_M)
        self.min_context_buffer_spin.setSuffix(" m")
        self.min_context_buffer_spin.setToolTip(
            "지도가 표현할 지상 영역의 최소 범위(m)입니다.\n"
            "유적이 작아 과도하게 줌인되는 것을 방지하고 최소한 이 거리의 지형을 보장합니다 (0 = 사용 안 함)."
        )

        self.use_standard_scales_checkbox = QCheckBox("정규 축척 사용")
        self.use_standard_scales_checkbox.setChecked(True)
        self.use_standard_scales_checkbox.setToolTip(
            "도면 축척을 임의 소수점 대신 1:1,000, 1:5,000 같은 정규 표준 축척 단계로 올림 적용합니다."
        )

        # 점유율 및 정규 축척 설정 행
        occupancy_row = QHBoxLayout()
        occupancy_row.setSpacing(10)
        occupancy_row.addWidget(self.target_occupancy_spin)
        occupancy_row.addWidget(self.use_standard_scales_checkbox)
        occupancy_container = QWidget()
        occupancy_container.setLayout(occupancy_row)

        self.layout_mode_combo = QComboBox()
        self.layout_mode_combo.addItem("기존 Layout 사용", EXISTING_LAYOUT_MODE)
        self.layout_mode_combo.addItem("자동 Layout 생성", AUTO_LAYOUT_MODE)

        self.layout_name_combo = QComboBox()
        self.map_item_id_combo = QComboBox()
        self.refresh_layouts_button = QPushButton("↻ 새로고침")
        self.refresh_layouts_button.setObjectName("NeutralButton")
        self.refresh_layouts_button.setFixedWidth(90)

        def _lbl(text, important=False):
            return _make_label(text, important)

        # 외곽선 레이어 행: 콤보박스 + 잠금 버튼
        outline_row = QHBoxLayout()
        outline_row.setSpacing(4)
        outline_row.addWidget(self.outline_layer_combo)
        outline_row.addWidget(self.outline_lock_btn)
        outline_container = QWidget()
        outline_container.setLayout(outline_row)

        # 레이어 순서: 외곽선 → 채움 → 배경 (시각 스택 순서)
        rows = [
            ("유적 외곽선", outline_container, True),
            ("유적 채움", self.fill_layer_combo, False),
            ("배경 레이어", self.base_layer_combo, False),
            ("유적명 필드", self.name_field_combo, False),
            ("면적 필드", self.area_field_combo, False),
            ("도면 내 유적 점유율", occupancy_container, False),
            ("최소 지형 맥락 거리", self.min_context_buffer_spin, False),
            ("출력 CRS", self.output_crs_edit, False),
            ("Layout 모드", self.layout_mode_combo, False),
            ("Layout 이름", self.layout_name_combo, False),
            ("Map Item ID", self.map_item_id_combo, False),
        ]
        layout_name_row = 8  # fallback
        for row_idx, (label_text, widget, important) in enumerate(rows):
            layout.addWidget(_lbl(label_text, important), row_idx, 0, Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(widget, row_idx, 1)
            if widget == self.layout_name_combo:
                layout_name_row = row_idx

        layout.addWidget(self.refresh_layouts_button, layout_name_row, 2)

        return group

    def _toggle_outline_lock(self):
        self._outline_locked = not self._outline_locked
        self.outline_layer_combo.setEnabled(not self._outline_locked)
        self.outline_lock_btn.setText("🔒" if self._outline_locked else "🔓")
        self.outline_lock_btn.setToolTip(
            OUTLINE_LOCK_TOOLTIP if self._outline_locked else OUTLINE_UNLOCK_TOOLTIP
        )

    def _build_style_group(self):
        self.style_group = CollapsibleSection("표현 설정 (선택)")

        note = QLabel(
            "기본값은 원래 레이어 심볼을 사용합니다. "
            "체크 시 이번 출력에 한해 채움색/외곽선을 덮어씁니다."
        )
        note.setObjectName("HelpText")
        note.setWordWrap(True)

        self.fill_color_button = QPushButton()
        self.fill_color_button.setObjectName("ColorButton")
        self.outline_color_button = QPushButton()
        self.outline_color_button.setObjectName("ColorButton")
        self.outline_width_spin = QDoubleSpinBox()
        self.outline_width_spin.setRange(MIN_OUTLINE_WIDTH_MM, MAX_OUTLINE_WIDTH_MM)
        self.outline_width_spin.setSingleStep(OUTLINE_WIDTH_STEP_MM)
        self.outline_width_spin.setValue(DEFAULT_OUTLINE_WIDTH_MM)
        self.outline_width_spin.setSuffix(OUTLINE_WIDTH_SUFFIX)

        self._apply_button_color(self.fill_color_button, self._fill_color)
        self._apply_button_color(self.outline_color_button, self._outline_color)

        self.attribute_style_checkbox = QCheckBox("속성값별 채움색 사용")
        self.attribute_style_field_combo = QComboBox()
        self.attribute_style_field_combo.addItem(ATTRIBUTE_STYLE_NONE_LABEL, "")

        self.style_rules_container = QWidget()
        self.style_rules_layout = QVBoxLayout(self.style_rules_container)
        self.style_rules_layout.setContentsMargins(0, 0, 0, 0)
        self.style_rules_layout.setSpacing(6)

        self.add_style_rule_button = QPushButton("＋  색상 규칙 추가")
        self.add_style_rule_button.setObjectName("NeutralButton")

        rules_help = QLabel("일치하지 않는 속성값은 기본 채움색을 사용합니다.")
        rules_help.setObjectName("HelpText")
        rules_help.setWordWrap(True)

        rules_box = QWidget()
        rb_layout = QVBoxLayout(rules_box)
        rb_layout.setContentsMargins(0, 0, 0, 0)
        rb_layout.setSpacing(6)
        rb_layout.addWidget(self.attribute_style_checkbox)
        rb_layout.addWidget(self.attribute_style_field_combo)
        rb_layout.addWidget(self.style_rules_container)
        rb_layout.addWidget(self.add_style_rule_button, alignment=Qt.AlignLeft)
        rb_layout.addWidget(rules_help)

        self.style_group.add_full_row(note)
        self.style_group.add_row("기본 채움색", self.fill_color_button)
        self.style_group.add_row("외곽선 색", self.outline_color_button)
        self.style_group.add_row("외곽선 두께", self.outline_width_spin)
        self.style_group.add_row("속성값별 채움색", rules_box)
        return self.style_group

    def _build_preview_group(self):
        group = QGroupBox("미리보기")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # 검색 + 선택 행
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.feature_search_edit = QLineEdit()
        self.feature_search_edit.setPlaceholderText(FEATURE_SEARCH_INPUT_PLACEHOLDER)
        self.feature_combo = QComboBox()
        self.feature_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        search_row.addWidget(self.feature_search_edit, 2)
        search_row.addWidget(self.feature_combo, 3)

        self.preview_button = QPushButton("▶  미리보기")
        self.preview_button.setObjectName("PrimaryButton")
        self.preview_button.setMinimumHeight(34)
        search_row.addWidget(self.preview_button)

        # 미리보기 이미지 + 사이드 패널
        preview_row = QHBoxLayout()
        preview_row.setSpacing(10)

        self.preview_image_label = QLabel("미리보기 이미지")
        self.preview_image_label.setObjectName("PreviewFrame")
        self.preview_image_label.setAlignment(Qt.AlignCenter)
        self.preview_image_label.setMinimumSize(
            DOCK_DIMENSIONS.preview_min_width, DOCK_DIMENSIONS.preview_min_height,
        )
        self.preview_image_label.setWordWrap(True)

        side_panel = QVBoxLayout()
        side_panel.setSpacing(8)
        occ_title = _SectionLabel("도면 점유율")
        side_panel.addWidget(occ_title)
        self.occupancy_widget = OccupancyDiagramWidget()
        side_panel.addWidget(self.occupancy_widget)

        self.metrics_label = QLabel("가로 점유율: -\n세로 점유율: -\n판정: -\n축척: -\n면적: -")
        self.metrics_label.setObjectName("InfoCard")
        self.metrics_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        side_panel.addWidget(self.metrics_label)
        side_panel.addStretch(1)

        preview_row.addWidget(self.preview_image_label, 3)
        preview_row.addLayout(side_panel, 2)

        layout.addLayout(search_row)
        layout.addLayout(preview_row)
        return group

    def _build_export_group(self):
        group = QGroupBox("출력")
        layout = QGridLayout(group)
        layout.setSpacing(8)
        layout.setColumnStretch(1, 1)

        self.output_mode_combo = QComboBox()
        self.output_mode_combo.addItem("최종도면 1장", OUTPUT_MODE_FINAL_ONLY)
        self.output_mode_combo.addItem("배경도 + 유적도 2장", OUTPUT_MODE_PAIRED)

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("출력 폴더 경로...")
        self.output_dir_button = QPushButton("📁  폴더")
        self.output_dir_button.setObjectName("NeutralButton")
        self.output_dir_button.setFixedWidth(80)

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(MIN_DPI, MAX_DPI)
        self.dpi_spin.setValue(DEFAULT_DPI)
        self.dpi_spin.setSuffix(" dpi")

        self.export_current_button = QPushButton("⬇  현재 유적 출력")
        self.export_current_button.setObjectName("PrimaryButton")
        self.export_current_button.setMinimumHeight(34)
        self.export_all_button = QPushButton("⬇  전체 일괄 출력")
        self.export_all_button.setObjectName("AccentButton")
        self.export_all_button.setMinimumHeight(34)
        self.progress_label = QLabel("대기 중")
        self.progress_label.setObjectName("StatusPill")
        self.progress_label.setAlignment(Qt.AlignCenter)

        def _lbl(text):
            return _make_label(text)

        layout.addWidget(_lbl("출력 방식"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.output_mode_combo, 0, 1, 1, 2)
        layout.addWidget(_lbl("출력 폴더"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.output_dir_edit, 1, 1)
        layout.addWidget(self.output_dir_button, 1, 2)
        layout.addWidget(_lbl("DPI"), 2, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.dpi_spin, 2, 1, 1, 2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self.export_current_button, 1)
        btn_row.addWidget(self.export_all_button, 1)
        layout.addLayout(btn_row, 3, 0, 1, 3)
        layout.addWidget(self.progress_label, 4, 0, 1, 3)

        return group

    def _build_log_group(self):
        group = QGroupBox("로그")
        layout = QVBoxLayout(group)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(DOCK_DIMENSIONS.log_min_height)
        self.log_edit.setPlaceholderText("미리보기와 출력 진행 상황이 여기에 표시됩니다.")
        self.log_edit.setStyleSheet(
            f"font-family: 'Consolas', 'D2Coding', monospace; font-size: 11px; "
            f"color: {DOCK_PALETTE.text_soft};"
        )
        layout.addWidget(self.log_edit)
        return group

    # ──────────────────────────────────────────────────────────────
    #  시그널 연결
    # ──────────────────────────────────────────────────────────────

    def _connect_signals(self):
        self.fill_layer_combo.layerChanged.connect(self._on_fill_layer_changed)
        self.outline_layer_combo.layerChanged.connect(self._persist_state)
        self.base_layer_combo.layerChanged.connect(self._persist_state)
        self.name_field_combo.currentIndexChanged.connect(self._on_name_field_changed)
        self.area_field_combo.currentIndexChanged.connect(self._persist_state)
        self.feature_search_edit.textChanged.connect(self._schedule_feature_refresh)
        self.feature_combo.currentIndexChanged.connect(self._update_feature_actions)
        self.preview_button.clicked.connect(self._on_preview_clicked)
        self.output_dir_button.clicked.connect(self._choose_output_dir)
        self.export_current_button.clicked.connect(self._on_export_current_clicked)
        self.export_all_button.clicked.connect(self._on_export_all_clicked)
        self.layout_mode_combo.currentIndexChanged.connect(self._on_layout_mode_changed)
        self.layout_name_combo.currentIndexChanged.connect(self._refresh_map_item_ids)
        self.map_item_id_combo.currentIndexChanged.connect(self._persist_state)
        self.refresh_layouts_button.clicked.connect(self._refresh_layouts)
        self.fill_color_button.clicked.connect(self._select_fill_color)
        self.outline_color_button.clicked.connect(self._select_outline_color)
        self.output_crs_edit.editingFinished.connect(self._persist_state)
        self.output_mode_combo.currentIndexChanged.connect(self._persist_state)
        self.dpi_spin.valueChanged.connect(self._persist_state)
        self.outline_width_spin.valueChanged.connect(self._persist_state)
        self.target_occupancy_spin.valueChanged.connect(self._persist_state)
        self.min_context_buffer_spin.valueChanged.connect(self._persist_state)
        self.use_standard_scales_checkbox.toggled.connect(self._persist_state)
        self.style_group.toggled.connect(self._on_style_group_toggled)
        self.attribute_style_checkbox.toggled.connect(self._on_attribute_style_toggled)
        self.attribute_style_field_combo.currentIndexChanged.connect(self._persist_state)
        self.add_style_rule_button.clicked.connect(self._on_add_style_rule_clicked)

    def _apply_theme(self):
        self.setStyleSheet(build_dock_stylesheet(DOCK_PALETTE))

    # ──────────────────────────────────────────────────────────────
    #  슬롯
    # ──────────────────────────────────────────────────────────────

    def _on_fill_layer_changed(self):
        self._refresh_fields()
        self._schedule_feature_refresh()
        self._persist_state()

    def _on_name_field_changed(self):
        self._schedule_feature_refresh()
        self._persist_state()

    def _on_layout_mode_changed(self, *_args):
        use_existing = self.layout_mode_combo.currentData() == EXISTING_LAYOUT_MODE
        self.layout_name_combo.setEnabled(use_existing)
        self.map_item_id_combo.setEnabled(use_existing)
        self.refresh_layouts_button.setEnabled(use_existing)
        self._persist_state()

    def _on_style_group_toggled(self, *_args):
        self._sync_style_controls()
        self._persist_state()

    def _on_attribute_style_toggled(self, *_args):
        self._sync_style_controls()
        self._persist_state()

    def _sync_style_controls(self):
        enabled = self.style_group.isChecked()
        self.fill_color_button.setEnabled(enabled)
        self.outline_color_button.setEnabled(enabled)
        self.outline_width_spin.setEnabled(enabled)
        attribute_enabled = enabled and self.attribute_style_checkbox.isChecked()
        self.attribute_style_checkbox.setEnabled(enabled)
        self.attribute_style_field_combo.setEnabled(attribute_enabled)
        self.add_style_rule_button.setEnabled(attribute_enabled)
        self.style_rules_container.setVisible(attribute_enabled)
        for row in self._style_rule_rows:
            row.set_controls_enabled(attribute_enabled)

    def _schedule_feature_refresh(self):
        if self._is_loading_state:
            return
        self._search_timer.start()

    def _on_add_style_rule_clicked(self):
        self._add_style_rule_row()
        self._sync_style_controls()
        self._persist_state()

    def _set_feature_placeholder(self, text: str):
        self.feature_combo.blockSignals(True)
        self.feature_combo.clear()
        self.feature_combo.addItem(text, None)
        self.feature_combo.setCurrentIndex(0)
        self.feature_combo.blockSignals(False)

    def _update_feature_actions(self):
        has_feature = self.feature_combo.currentData() is not None
        self.preview_button.setEnabled(has_feature)
        self.export_current_button.setEnabled(has_feature)

    def _refresh_fields(self):
        layer = self.fill_layer_combo.currentLayer()
        saved_name_field = self.name_field_combo.currentText()
        saved_area_field = self.area_field_combo.currentData() or ""
        saved_style_field = self.attribute_style_field_combo.currentData() or ""
        self.name_field_combo.blockSignals(True)
        self.area_field_combo.blockSignals(True)
        self.attribute_style_field_combo.blockSignals(True)
        self.name_field_combo.clear()
        self.area_field_combo.clear()
        self.attribute_style_field_combo.clear()
        self.area_field_combo.addItem(GEOMETRY_AREA_LABEL, "")
        self.attribute_style_field_combo.addItem(ATTRIBUTE_STYLE_NONE_LABEL, "")

        if layer is not None:
            for field in layer.fields():
                self.name_field_combo.addItem(field.name())
                self.area_field_combo.addItem(field.name(), field.name())
                self.attribute_style_field_combo.addItem(field.name(), field.name())

        if saved_name_field:
            index = self.name_field_combo.findText(saved_name_field)
            if index >= 0:
                self.name_field_combo.setCurrentIndex(index)
        if saved_area_field:
            index = self.area_field_combo.findData(saved_area_field)
            if index >= 0:
                self.area_field_combo.setCurrentIndex(index)
        if saved_style_field:
            index = self.attribute_style_field_combo.findData(saved_style_field)
            if index >= 0:
                self.attribute_style_field_combo.setCurrentIndex(index)

        self.name_field_combo.blockSignals(False)
        self.area_field_combo.blockSignals(False)
        self.attribute_style_field_combo.blockSignals(False)

    def _refresh_feature_choices(self):
        fill_layer = self.fill_layer_combo.currentLayer()
        name_field = self.name_field_combo.currentText().strip()
        if fill_layer is None or not name_field:
            self._set_feature_placeholder(FEATURE_SELECT_PLACEHOLDER)
            self._update_feature_actions()
            return

        search_text = self.feature_search_edit.text().strip()
        if len(search_text) < MIN_FEATURE_SEARCH_CHARS:
            self._set_feature_placeholder(FEATURE_SEARCH_PLACEHOLDER)
            self._update_feature_actions()
            return

        self.feature_combo.blockSignals(True)
        current_feature_id = self.feature_combo.currentData()
        self.feature_combo.clear()

        choices = self.engine.list_feature_choices(fill_layer.id(), name_field, search_text)
        if not choices:
            self.feature_combo.addItem(FEATURE_NO_RESULTS_PLACEHOLDER, None)
            self.feature_combo.blockSignals(False)
            self._update_feature_actions()
            return

        for choice in choices:
            self.feature_combo.addItem(choice.label, choice.feature_id)

        if current_feature_id is not None:
            index = self.feature_combo.findData(current_feature_id)
            if index >= 0:
                self.feature_combo.setCurrentIndex(index)

        self.feature_combo.blockSignals(False)
        self._update_feature_actions()

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
        path = QFileDialog.getExistingDirectory(self, OUTPUT_DIRECTORY_DIALOG_TITLE, current)
        if path:
            self.output_dir_edit.setText(path)
            self._persist_state()

    def _select_fill_color(self):
        self._select_color("fill")

    def _select_outline_color(self):
        self._select_color("outline")

    def _select_color(self, target: str):
        current = self._fill_color if target == "fill" else self._outline_color
        color = QColorDialog.getColor(current, self, COLOR_DIALOG_TITLE)
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
        foreground = (
            COLOR_BUTTON_TEXT_DARK
            if color.lightness() < COLOR_BUTTON_LIGHTNESS_THRESHOLD
            else COLOR_BUTTON_TEXT_LIGHT
        )
        button.setStyleSheet(
            build_color_button_stylesheet(color.name(), foreground, DOCK_PALETTE.color_button_border)
        )

    def _add_style_rule_row(self, value: str = "", fill_color_hex: str = DEFAULT_FILL_COLOR_HEX):
        row = AttributeRuleRow(value=value, fill_color_hex=fill_color_hex, parent=self.style_rules_container)
        row.changed.connect(self._persist_state)
        row.removed.connect(self._remove_style_rule_row)
        self._style_rule_rows.append(row)
        self.style_rules_layout.addWidget(row)
        return row

    def _remove_style_rule_row(self, row):
        if row not in self._style_rule_rows:
            return
        self._style_rule_rows.remove(row)
        self.style_rules_layout.removeWidget(row)
        row.deleteLater()
        self._persist_state()

    def _clear_style_rule_rows(self):
        for row in list(self._style_rule_rows):
            self.style_rules_layout.removeWidget(row)
            row.deleteLater()
        self._style_rule_rows.clear()

    def _collect_style_rules(self) -> tuple[AttributeColorRule, ...]:
        rules: list[AttributeColorRule] = []
        for row in self._style_rule_rows:
            rule = row.to_rule()
            if rule is not None:
                rules.append(rule)
        return tuple(rules)

    def _update_preview_pixmap(self):
        if self._preview_pixmap is None:
            return
        self.preview_image_label.setPixmap(
            self._preview_pixmap.scaled(
                self.preview_image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
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
        self._preview_pixmap = QPixmap(preview.image_path)
        self._update_preview_pixmap()
        self.occupancy_widget.set_ratio(preview.circle_ratio)
        self.metrics_label.setText(
            "\n".join([
                f"가로 점유율: {preview.width_ratio * 100:.1f}%",
                f"세로 점유율: {preview.height_ratio * 100:.1f}%",
                f"판정: {preview.occupancy_label}",
                f"축척: 1:{preview.scale:,}",
                f"면적: {preview.area_m2:,.1f}㎡",
            ])
        )
        self.progress_label.setText(f"✓ 미리보기 완료: {preview.name}")
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

        self.progress_label.setText(f"✓ 출력 완료 ({len(paths)}개)")
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
            self.progress_label.setText(f"[{index}/{total}]  {name}")
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
            f"✓ 완료: 성공 {summary.exported} / 실패 {summary.failed}"
        )
        self.log(
            f"일괄 출력 완료: 총 {summary.total}, 성공 {summary.exported}, 실패 {summary.failed}"
        )

    def _current_feature_id(self) -> int:
        feature_id = self.feature_combo.currentData()
        if feature_id is None:
            raise ValueError("현재 유적이 선택되지 않았습니다.")
        return int(feature_id)

    def _current_layer_id(self, combo: QgsMapLayerComboBox) -> str:
        layer = combo.currentLayer()
        return layer.id() if layer is not None else ""

    def _restore_combo_text(self, combo: QComboBox, value: str):
        if not value:
            return
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _restore_combo_data(self, combo: QComboBox, value):
        if value in (None, ""):
            return
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _serialize_style_rules(self) -> list[dict[str, str]]:
        return [
            {"value": rule.value, "fill_color_hex": rule.fill_color_hex}
            for rule in self._collect_style_rules()
        ]

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
        area_field = area_field or None

        layout_mode = self.layout_mode_combo.currentData()
        layout_name = self.layout_name_combo.currentText().strip()
        map_item_id = self.map_item_id_combo.currentText().strip()
        if layout_mode == EXISTING_LAYOUT_MODE:
            if not layout_name:
                raise ValueError("기존 Layout 이름을 선택하세요.")
            if not map_item_id:
                raise ValueError("Map Item ID를 선택하세요.")

        output_dir = self.output_dir_edit.text().strip()
        if require_output_dir and not output_dir:
            raise ValueError("출력 폴더를 지정하세요.")

        attribute_field = ""
        attribute_rules: tuple[AttributeColorRule, ...] = ()
        if self.style_group.isChecked() and self.attribute_style_checkbox.isChecked():
            attribute_field = self.attribute_style_field_combo.currentData() or ""
            attribute_rules = self._collect_style_rules()

        return ExportConfig(
            base_layer_id=base_layer.id(),
            fill_layer_id=fill_layer.id(),
            outline_layer_id=(self._current_layer_id(self.outline_layer_combo) or None),
            name_field=name_field,
            area_field=area_field,
            output_crs_authid=(self.output_crs_edit.text().strip() or DEFAULT_OUTPUT_CRS_AUTHID),
            style=StyleConfig(
                enabled=self.style_group.isChecked(),
                fill_color_hex=self._fill_color.name(),
                outline_color_hex=self._outline_color.name(),
                outline_width_mm=self.outline_width_spin.value(),
                attribute_field=attribute_field,
                attribute_color_rules=attribute_rules,
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
            target_occupancy_ratio=self.target_occupancy_spin.value() / 100.0,
            min_context_buffer_m=self.min_context_buffer_spin.value(),
            use_standard_scales=self.use_standard_scales_checkbox.isChecked(),
        )

    def _persist_state(self):
        if self._is_loading_state:
            return
        self.settings.set(SettingsKey.BASE_LAYER_ID, self._current_layer_id(self.base_layer_combo))
        self.settings.set(SettingsKey.FILL_LAYER_ID, self._current_layer_id(self.fill_layer_combo))
        self.settings.set(SettingsKey.OUTLINE_LAYER_ID, self._current_layer_id(self.outline_layer_combo))
        self.settings.set(SettingsKey.NAME_FIELD, self.name_field_combo.currentText())
        self.settings.set(SettingsKey.AREA_FIELD, self.area_field_combo.currentData() or "")
        self.settings.set(SettingsKey.OUTPUT_CRS_AUTHID, self.output_crs_edit.text().strip())
        self.settings.set(SettingsKey.LAYOUT_MODE, self.layout_mode_combo.currentData())
        self.settings.set(SettingsKey.LAYOUT_NAME, self.layout_name_combo.currentText())
        self.settings.set(SettingsKey.MAP_ITEM_ID, self.map_item_id_combo.currentText())
        self.settings.set(SettingsKey.STYLE_ENABLED, self.style_group.isChecked())
        self.settings.set(SettingsKey.STYLE_ATTRIBUTE_ENABLED, self.attribute_style_checkbox.isChecked())
        self.settings.set(SettingsKey.STYLE_ATTRIBUTE_FIELD, self.attribute_style_field_combo.currentData() or "")
        self.settings.set_json(SettingsKey.STYLE_ATTRIBUTE_RULES, self._serialize_style_rules())
        self.settings.set(SettingsKey.FILL_COLOR_HEX, self._fill_color.name())
        self.settings.set(SettingsKey.OUTLINE_COLOR_HEX, self._outline_color.name())
        self.settings.set(SettingsKey.OUTLINE_WIDTH_MM, self.outline_width_spin.value())
        self.settings.set(SettingsKey.FEATURE_SEARCH, self.feature_search_edit.text())
        self.settings.set(SettingsKey.OUTPUT_MODE, self.output_mode_combo.currentData())
        self.settings.set(SettingsKey.OUTPUT_DIR, self.output_dir_edit.text().strip())
        self.settings.set(SettingsKey.DPI, self.dpi_spin.value())
        self.settings.set(SettingsKey.TARGET_OCCUPANCY_RATIO, self.target_occupancy_spin.value())
        self.settings.set(SettingsKey.MIN_CONTEXT_BUFFER_M, self.min_context_buffer_spin.value())
        self.settings.set(SettingsKey.USE_STANDARD_SCALES, self.use_standard_scales_checkbox.isChecked())

    def _load_state(self):
        self._set_layer_if_present(self.base_layer_combo, self.settings.get(SettingsKey.BASE_LAYER_ID, ""))
        self._set_layer_if_present(self.fill_layer_combo, self.settings.get(SettingsKey.FILL_LAYER_ID, ""))
        self._set_layer_if_present(self.outline_layer_combo, self.settings.get(SettingsKey.OUTLINE_LAYER_ID, ""))

        self.output_crs_edit.setText(self.settings.get(SettingsKey.OUTPUT_CRS_AUTHID))
        self.feature_search_edit.blockSignals(True)
        self.feature_search_edit.setText(self.settings.get(SettingsKey.FEATURE_SEARCH, ""))
        self.feature_search_edit.blockSignals(False)
        self.output_dir_edit.setText(self.settings.get(SettingsKey.OUTPUT_DIR, ""))
        self.dpi_spin.setValue(self.settings.get_int(SettingsKey.DPI, DEFAULT_DPI))
        self.outline_width_spin.setValue(
            self.settings.get_float(SettingsKey.OUTLINE_WIDTH_MM, DEFAULT_OUTLINE_WIDTH_MM)
        )

        val = self.settings.get(SettingsKey.TARGET_OCCUPANCY_RATIO)
        if isinstance(val, float) and val <= 1.0:
            self.target_occupancy_spin.setValue(int(round(val * 100)))
        elif val is not None:
            self.target_occupancy_spin.setValue(int(val))
        else:
            self.target_occupancy_spin.setValue(int(DEFAULT_TARGET_OCCUPANCY_RATIO * 100))

        min_buf = self.settings.get_int(SettingsKey.MIN_CONTEXT_BUFFER_M, DEFAULT_MIN_CONTEXT_BUFFER_M)
        self.min_context_buffer_spin.setValue(min_buf)

        self.use_standard_scales_checkbox.setChecked(
            self.settings.get_bool(SettingsKey.USE_STANDARD_SCALES, True)
        )

        fill_color_hex = self.settings.get(SettingsKey.FILL_COLOR_HEX)
        outline_color_hex = self.settings.get(SettingsKey.OUTLINE_COLOR_HEX)
        self._fill_color = QColor(fill_color_hex)
        self._outline_color = QColor(outline_color_hex)
        self._apply_button_color(self.fill_color_button, self._fill_color)
        self._apply_button_color(self.outline_color_button, self._outline_color)
        self.style_group.setChecked(self.settings.get_bool(SettingsKey.STYLE_ENABLED, False))
        self.attribute_style_checkbox.setChecked(
            self.settings.get_bool(SettingsKey.STYLE_ATTRIBUTE_ENABLED, False)
        )

        layout_mode = self.settings.get(SettingsKey.LAYOUT_MODE, EXISTING_LAYOUT_MODE)
        self._restore_combo_data(self.layout_mode_combo, layout_mode)

        layout_name = self.settings.get(SettingsKey.LAYOUT_NAME, "")
        self._restore_combo_text(self.layout_name_combo, layout_name)

        self._refresh_map_item_ids()
        self._restore_combo_text(self.map_item_id_combo, self.settings.get(SettingsKey.MAP_ITEM_ID, ""))
        self._restore_combo_data(
            self.output_mode_combo, self.settings.get(SettingsKey.OUTPUT_MODE, OUTPUT_MODE_FINAL_ONLY)
        )
        self._on_layout_mode_changed()
        self._restore_combo_text(self.name_field_combo, self.settings.get(SettingsKey.NAME_FIELD, ""))
        self._restore_combo_data(self.area_field_combo, self.settings.get(SettingsKey.AREA_FIELD, ""))
        self._restore_combo_data(
            self.attribute_style_field_combo, self.settings.get(SettingsKey.STYLE_ATTRIBUTE_FIELD, "")
        )

        self._clear_style_rule_rows()
        rules = self.settings.get_json(SettingsKey.STYLE_ATTRIBUTE_RULES, []) or []
        for rule in rules:
            value = str(rule.get("value", "")).strip()
            if not value:
                continue
            fill_color_hex = (
                str(rule.get("fill_color_hex", DEFAULT_FILL_COLOR_HEX)).strip() or DEFAULT_FILL_COLOR_HEX
            )
            self._add_style_rule_row(value=value, fill_color_hex=fill_color_hex)

    def _set_layer_if_present(self, combo: QgsMapLayerComboBox, layer_id: str):
        if not layer_id:
            return
        layer = self.project.mapLayer(layer_id)
        if layer is not None:
            combo.setLayer(layer)

    def log(self, message: str):
        self.log_edit.appendPlainText(message)

    def _show_error(self, title: str, error: Exception):
        self.log(f"⚠ {title}: {error}")
        QMessageBox.warning(self, title, str(error))

    def _cleanup_preview_file(self):
        if self._preview_image_path and os.path.exists(self._preview_image_path):
            try:
                os.remove(self._preview_image_path)
            except OSError:
                pass
        self._preview_image_path = None
        self._preview_pixmap = None


def _make_label(text: str, important: bool = False, parent=None) -> QLabel:
    """소제목·레이블 헬퍼. important=True 이면 title 색상과 굵은 글씨를 사용한다."""
    label = QLabel(text, parent)
    if important:
        label.setStyleSheet(
            f"color: {DOCK_PALETTE.title}; font-size: 11px; font-weight: 700;"
        )
    else:
        label.setStyleSheet(f"color: {DOCK_PALETTE.text_soft}; font-size: 11px;")
    return label


def _SectionLabel(text: str, parent=None) -> QLabel:  # noqa: N802
    """그룹 내 소제목 레이블 (SectionCaption objectName 적용)."""
    label = QLabel(text, parent)
    label.setObjectName("SectionCaption")
    return label
