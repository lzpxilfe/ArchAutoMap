from __future__ import annotations

from dataclasses import dataclass

PLUGIN_NAME = "ArchAutoMap"
ICON_FILENAME = "icon.png"
ACTION_OBJECT_NAME = "ArchAutoMapAction"
TOOLBAR_OBJECT_NAME = "ArchAutoMapToolbar"
DOCK_WIDGET_OBJECT_NAME = "ArchAutoMapDockWidget"

SETTINGS_PREFIX = f"{PLUGIN_NAME}/"

DEFAULT_OUTPUT_CRS_AUTHID = "EPSG:5186"
DEFAULT_FILL_COLOR_HEX = "#6C8EBF"
DEFAULT_OUTLINE_COLOR_HEX = "#2D3A4A"
DEFAULT_OUTLINE_WIDTH_MM = 0.6
DEFAULT_DPI = 300
DEFAULT_PREVIEW_DPI = 120
AUTO_LAYOUT_WIDTH_MM = 105.0
AUTO_LAYOUT_HEIGHT_MM = 80.0

MIN_DPI = 72
MAX_DPI = 1200
MIN_OUTLINE_WIDTH_MM = 0.1
MAX_OUTLINE_WIDTH_MM = 5.0
OUTLINE_WIDTH_STEP_MM = 0.1
OUTLINE_WIDTH_SUFFIX = " mm"

OUTPUT_MODE_FINAL_ONLY = "final_only"
OUTPUT_MODE_PAIRED = "paired"
EXISTING_LAYOUT_MODE = "existing"
AUTO_LAYOUT_MODE = "auto"

AUTO_LAYOUT_NAME = "ArchAutoMap Preview"
AUTO_MAP_ITEM_ID = "archautomap_map"
LAYOUT_MILLIMETER_UNIT = "LayoutMillimeters"

SEARCH_DEBOUNCE_MS = 250
MIN_FEATURE_SEARCH_CHARS = 2
MAX_FEATURE_SEARCH_RESULTS = 200

FEATURE_SEARCH_PLACEHOLDER = "유적명 2글자 이상 입력"
FEATURE_SELECT_PLACEHOLDER = "레이어와 유적명 필드를 먼저 선택"
FEATURE_NO_RESULTS_PLACEHOLDER = "검색 결과 없음"
ATTRIBUTE_STYLE_NONE_LABEL = "속성값 기준 없음"
GEOMETRY_AREA_LABEL = "geometry 직접 계산"
OUTPUT_DIRECTORY_DIALOG_TITLE = "출력 폴더 선택"
COLOR_DIALOG_TITLE = "색상 선택"

MEMORY_LAYER_PROVIDER = "memory"
POLYGON_GEOMETRY_NAME = "Polygon"
MULTI_POLYGON_GEOMETRY_NAME = "MultiPolygon"
TRANSPARENT_FILL_COLOR = "0,0,0,0"
SYMBOL_SIZE_UNIT_MM = "MM"

COLOR_BUTTON_TEXT_LIGHT = "#F0F4FF"
COLOR_BUTTON_TEXT_DARK = "#0D1117"
COLOR_BUTTON_LIGHTNESS_THRESHOLD = 140


@dataclass(frozen=True)
class DockDimensions:
    width: int = 520
    min_height: int = 720
    initial_height: int = 860
    preview_min_width: int = 310
    preview_min_height: int = 230
    log_min_height: int = 120
    occupancy_widget_min_size: int = 130


@dataclass(frozen=True)
class OccupancyDiagramStyle:
    min_ratio: float = 0.05
    max_ratio: float = 0.98
    margin_px: int = 10
    frame_width_px: float = 1.5
    corner_radius_px: float = 10.0
    accent_outline_width_px: float = 1.0


@dataclass(frozen=True)
class DockPalette:
    # ── 배경/표면 ──────────────────────────────
    background: str = "#0D1117"        # GitHub dark 배경
    surface: str = "#161B22"           # 카드 배경
    surface_alt: str = "#1C2333"       # 입력창, 인포카드
    surface_muted: str = "#21262D"     # 호버 표면
    surface_hover: str = "#2D333B"     # 호버

    # ── 텍스트 ────────────────────────────────
    text: str = "#E6EDF3"              # 기본 텍스트
    text_soft: str = "#8B949E"         # 보조 텍스트
    text_muted: str = "#6E7681"        # 설명 텍스트
    text_disabled: str = "#484F58"     # 비활성

    # ── 타이틀 / 강조 색 ─────────────────────
    title: str = "#79C0FF"             # 파란 accent 텍스트
    checkbox: str = "#CDD9E5"

    # ── 테두리 ───────────────────────────────
    border: str = "#30363D"
    border_soft: str = "#21262D"
    border_focus: str = "#388BFD"
    checkbox_border: str = "#30363D"

    # ── 버튼 accent (파란 계열) ───────────────
    accent: str = "#388BFD"            # primary blue
    accent_hover: str = "#58A6FF"

    # ── neutral 버튼 ──────────────────────────
    neutral: str = "#2D333B"
    neutral_hover: str = "#3D444D"
    neutral_text: str = "#CDD9E5"

    # ── default 버튼 ─────────────────────────
    button_default: str = "#21262D"
    button_default_hover: str = "#2D333B"
    button_disabled: str = "#161B22"

    # ── 기타 ────────────────────────────────
    color_button_border: str = "#30363D"
    diagram_frame: str = "#30363D"
    diagram_bg: str = "#161B22"

    # ── 위험/강조 버튼 ────────────────────────
    accent2: str = "#2EA043"           # 일괄출력 green
    accent2_hover: str = "#3FB950"


DOCK_DIMENSIONS = DockDimensions()
DOCK_PALETTE = DockPalette()
OCCUPANCY_DIAGRAM_STYLE = OccupancyDiagramStyle()


def build_color_button_stylesheet(
    background_hex: str,
    foreground_hex: str,
    border_hex: str,
) -> str:
    return (
        "QPushButton {"
        f"background-color: {background_hex};"
        f"color: {foreground_hex};"
        f"border: 1px solid {border_hex};"
        "border-radius: 8px;"
        "padding: 6px 10px;"
        "font-weight: 600;}"
    )


def build_dock_stylesheet(palette: DockPalette = DOCK_PALETTE) -> str:
    return f"""
            * {{
                font-family: 'Segoe UI', 'Apple SD Gothic Neo', sans-serif;
            }}
            QWidget#{DOCK_WIDGET_OBJECT_NAME} {{
                background: {palette.background};
                color: {palette.text};
            }}
            QWidget#ArchAutoMapRoot {{
                background: {palette.background};
                color: {palette.text};
            }}
            QDialog {{
                background: {palette.background};
                color: {palette.text};
            }}
            QScrollArea {{
                border: none;
                background: {palette.background};
            }}
            QFrame#HeroCard {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1A2332,
                    stop:1 #162032
                );
                border: 1px solid {palette.border};
                border-radius: 14px;
            }}
            QGroupBox {{
                background: {palette.surface};
                border: 1px solid {palette.border};
                border-radius: 12px;
                margin-top: 18px;
                padding: 14px 12px 12px 12px;
                font-weight: 600;
                font-size: 12px;
                color: {palette.text};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: {palette.title};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }}
            QFrame#RuleRow {{
                background: {palette.surface_alt};
                border: 1px solid {palette.border};
                border-radius: 10px;
            }}
            QLabel#HeroTitle {{
                color: {palette.text};
                font-size: 18px;
                font-weight: 800;
                letter-spacing: -0.3px;
            }}
            QLabel#HeroSubtitle, QLabel#HelpText {{
                color: {palette.text_soft};
                font-size: 11px;
                line-height: 1.5;
            }}
            QLabel#SectionCaption {{
                color: {palette.title};
                font-weight: 700;
                font-size: 11px;
                letter-spacing: 0.3px;
            }}
            QLabel#InfoCard {{
                background: {palette.surface_alt};
                border: 1px solid {palette.border};
                border-radius: 10px;
                padding: 10px 12px;
                color: {palette.text_soft};
                font-size: 11px;
                line-height: 1.6;
            }}
            QLabel#StatusPill {{
                background: {palette.surface_alt};
                border: 1px solid {palette.border};
                border-radius: 8px;
                padding: 6px 12px;
                color: {palette.title};
                font-weight: 600;
                font-size: 11px;
            }}
            QLabel#PreviewFrame {{
                background: {palette.surface_alt};
                border: 1px solid {palette.border};
                border-radius: 10px;
                padding: 10px;
                color: {palette.text_muted};
            }}
            QLabel {{
                color: {palette.text};
                font-size: 12px;
            }}
            QCheckBox {{
                color: {palette.checkbox};
                spacing: 8px;
                font-weight: 600;
                font-size: 12px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid {palette.checkbox_border};
                background: {palette.surface_alt};
            }}
            QCheckBox::indicator:checked {{
                background: {palette.accent};
                border-color: {palette.accent_hover};
                image: none;
            }}
            QCheckBox::indicator:hover {{
                border-color: {palette.accent};
            }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
                background: {palette.surface_alt};
                color: {palette.text};
                border: 1px solid {palette.border};
                border-radius: 8px;
                padding: 6px 10px;
                selection-background-color: {palette.accent};
                font-size: 12px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
            QDoubleSpinBox:focus, QPlainTextEdit:focus {{
                border: 1px solid {palette.border_focus};
                background: {palette.surface_hover};
            }}
            QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
                border: 1px solid {palette.neutral_hover};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {palette.text_soft};
                margin-right: 6px;
            }}
            QComboBox QAbstractItemView {{
                background: {palette.surface};
                color: {palette.text};
                border: 1px solid {palette.border};
                border-radius: 8px;
                selection-background-color: {palette.accent};
                outline: none;
            }}
            QPushButton {{
                background: {palette.button_default};
                color: {palette.neutral_text};
                border: 1px solid {palette.border};
                border-radius: 8px;
                padding: 7px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {palette.button_default_hover};
                border-color: {palette.neutral_hover};
            }}
            QPushButton#PrimaryButton {{
                background: {palette.accent};
                color: white;
                border: none;
            }}
            QPushButton#PrimaryButton:hover {{
                background: {palette.accent_hover};
            }}
            QPushButton#AccentButton {{
                background: {palette.accent2};
                color: white;
                border: none;
            }}
            QPushButton#AccentButton:hover {{
                background: {palette.accent2_hover};
            }}
            QPushButton#NeutralButton {{
                background: {palette.neutral};
                color: {palette.neutral_text};
                border: 1px solid {palette.border};
            }}
            QPushButton#NeutralButton:hover {{
                background: {palette.neutral_hover};
            }}
            QPushButton:disabled {{
                background: {palette.button_disabled};
                color: {palette.text_disabled};
                border-color: {palette.border};
            }}
            QGroupBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid {palette.checkbox_border};
                background: {palette.surface_alt};
            }}
            QGroupBox::indicator:checked {{
                background: {palette.accent};
                border-color: {palette.accent_hover};
            }}
            QScrollBar:vertical {{
                background: {palette.background};
                width: 8px;
                border-radius: 4px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {palette.border};
                border-radius: 4px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {palette.text_muted};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: {palette.background};
                height: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {palette.border};
                border-radius: 4px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QPushButton#CollapsibleHeader {{
                background: {palette.surface};
                color: {palette.title};
                border: 1px solid {palette.border};
                border-radius: 6px;
                padding: 3px 10px;
                text-align: left;
                font-weight: 700;
                font-size: 11px;
            }}
            QPushButton#CollapsibleHeader:checked {{
                background: {palette.surface_alt};
                border-color: {palette.border_focus};
                border-bottom-left-radius: 0;
                border-bottom-right-radius: 0;
            }}
            QPushButton#CollapsibleHeader:hover {{
                background: {palette.surface_hover};
                border-color: {palette.neutral_hover};
            }}
            QWidget#CollapsibleContent {{
                background: {palette.surface};
                border: 1px solid {palette.border_focus};
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }}
            """

