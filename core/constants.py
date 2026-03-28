from __future__ import annotations

from dataclasses import dataclass

PLUGIN_NAME = "ArchAutoMap"
ICON_FILENAME = "icon.png"
ACTION_OBJECT_NAME = "ArchAutoMapAction"
TOOLBAR_OBJECT_NAME = "ArchAutoMapToolbar"
DOCK_WIDGET_OBJECT_NAME = "ArchAutoMapDockWidget"

SETTINGS_PREFIX = f"{PLUGIN_NAME}/"

DEFAULT_OUTPUT_CRS_AUTHID = "EPSG:5186"
DEFAULT_FILL_COLOR_HEX = "#C66B3D"
DEFAULT_OUTLINE_COLOR_HEX = "#3F332A"
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

COLOR_BUTTON_TEXT_LIGHT = "#1f1f1f"
COLOR_BUTTON_TEXT_DARK = "#ffffff"
COLOR_BUTTON_LIGHTNESS_THRESHOLD = 140


@dataclass(frozen=True)
class DockDimensions:
    width: int = 520
    min_height: int = 720
    initial_height: int = 860
    preview_min_width: int = 310
    preview_min_height: int = 230
    log_min_height: int = 150
    occupancy_widget_min_size: int = 140


@dataclass(frozen=True)
class OccupancyDiagramStyle:
    min_ratio: float = 0.05
    max_ratio: float = 0.98
    margin_px: int = 10
    frame_width_px: float = 2.0
    corner_radius_px: float = 12.0
    accent_outline_width_px: float = 1.5


@dataclass(frozen=True)
class DockPalette:
    background: str = "#F5EFE6"
    surface: str = "#D9CBB4"
    surface_alt: str = "#FBF7F0"
    surface_muted: str = "#E9DFD1"
    text: str = "#30261E"
    text_soft: str = "#5B4D40"
    text_muted: str = "#6B5B4D"
    text_disabled: str = "#6E6156"
    title: str = "#7A4A31"
    checkbox: str = "#4A3F35"
    border: str = "#C4B39A"
    border_soft: str = "#BCA992"
    checkbox_border: str = "#A99079"
    accent: str = "#C66B3D"
    accent_hover: str = "#B45D32"
    neutral: str = "#8C7967"
    neutral_hover: str = "#7B6857"
    button_default: str = "#A48F7A"
    button_default_hover: str = "#927B66"
    button_disabled: str = "#CCBDAA"
    color_button_border: str = "#9D8A76"
    diagram_frame: str = "#BDAE98"


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
        "border-radius: 10px;"
        "padding: 8px 12px;"
        "font-weight: 700;}"
    )


def build_dock_stylesheet(palette: DockPalette = DOCK_PALETTE) -> str:
    return f"""
            QWidget#{DOCK_WIDGET_OBJECT_NAME} {{
                background: {palette.background};
                color: {palette.text};
            }}
            QWidget#ArchAutoMapRoot {{
                background: {palette.background};
                color: {palette.text};
            }}
            QScrollArea {{
                border: none;
                background: {palette.background};
            }}
            QFrame#HeroCard, QGroupBox {{
                background: {palette.surface};
                border: 1px solid {palette.border};
                border-radius: 16px;
            }}
            QFrame#RuleRow {{
                background: {palette.surface_alt};
                border: 1px solid {palette.border};
                border-radius: 14px;
            }}
            QGroupBox {{
                margin-top: 16px;
                padding: 14px 12px 12px 12px;
                font-weight: 700;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {palette.title};
            }}
            QLabel#HeroTitle {{
                color: {palette.title};
                font-size: 20px;
                font-weight: 800;
            }}
            QLabel#HeroSubtitle, QLabel#HelpText {{
                color: {palette.text_soft};
                font-size: 12px;
            }}
            QCheckBox {{
                color: {palette.checkbox};
                spacing: 8px;
                font-weight: 700;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 5px;
                border: 1px solid {palette.checkbox_border};
                background: {palette.surface_alt};
            }}
            QCheckBox::indicator:checked {{
                background: {palette.accent};
                border-color: {palette.accent_hover};
            }}
            QLabel#SectionCaption {{
                color: {palette.title};
                font-weight: 700;
            }}
            QLabel#InfoCard, QLabel#StatusPill, QLabel#PreviewFrame {{
                background: {palette.surface_alt};
                border: 1px solid {palette.border};
                border-radius: 14px;
                padding: 10px 12px;
            }}
            QLabel#StatusPill {{
                color: {palette.title};
                font-weight: 700;
            }}
            QLabel#PreviewFrame {{
                color: {palette.text_muted};
            }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
                background: {palette.surface_alt};
                border: 1px solid {palette.border_soft};
                border-radius: 10px;
                padding: 6px 8px;
                selection-background-color: {palette.accent};
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
            QDoubleSpinBox:focus, QPlainTextEdit:focus {{
                border: 1px solid {palette.accent};
            }}
            QPushButton {{
                background: {palette.button_default};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 8px 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {palette.button_default_hover};
            }}
            QPushButton#PrimaryButton, QPushButton#AccentButton {{
                background: {palette.accent};
            }}
            QPushButton#PrimaryButton:hover,
            QPushButton#AccentButton:hover {{
                background: {palette.accent_hover};
            }}
            QPushButton#NeutralButton {{
                background: {palette.neutral};
            }}
            QPushButton#NeutralButton:hover {{
                background: {palette.neutral_hover};
            }}
            QPushButton:disabled {{
                background: {palette.button_disabled};
                color: {palette.text_disabled};
            }}
            QScrollBar:vertical {{
                background: {palette.surface_muted};
                width: 12px;
                border-radius: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {palette.accent};
                border-radius: 6px;
                min-height: 24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            """
