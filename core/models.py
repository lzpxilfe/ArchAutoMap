from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    AUTO_LAYOUT_HEIGHT_MM,
    AUTO_LAYOUT_WIDTH_MM,
    DEFAULT_DPI,
    DEFAULT_PREVIEW_DPI,
    OUTPUT_MODE_FINAL_ONLY,
)


@dataclass(frozen=True)
class AttributeColorRule:
    value: str
    fill_color_hex: str


@dataclass(frozen=True)
class StyleConfig:
    enabled: bool
    fill_color_hex: str
    outline_color_hex: str
    outline_width_mm: float
    attribute_field: str = ""
    attribute_color_rules: tuple[AttributeColorRule, ...] = ()


@dataclass(frozen=True)
class LayoutConfig:
    mode: str
    layout_name: str = ""
    map_item_id: str = ""
    page_width_mm: float = AUTO_LAYOUT_WIDTH_MM
    page_height_mm: float = AUTO_LAYOUT_HEIGHT_MM


@dataclass(frozen=True)
class ExportConfig:
    base_layer_id: str
    fill_layer_id: str
    outline_layer_id: str | None
    name_field: str
    area_field: str | None
    output_crs_authid: str
    style: StyleConfig
    layout: LayoutConfig
    dpi: int = DEFAULT_DPI
    output_mode: str = OUTPUT_MODE_FINAL_ONLY
    output_dir: str = ""
    preview_dpi: int = DEFAULT_PREVIEW_DPI
    target_occupancy_ratio: float = 0.60
    use_standard_scales: bool = True


@dataclass(frozen=True)
class FeatureChoice:
    feature_id: int
    name: str
    label: str


@dataclass(frozen=True)
class PreviewMetrics:
    name: str
    area_m2: float
    scale: int
    width_ratio: float
    height_ratio: float
    occupancy_ratio: float
    occupancy_label: str
    circle_ratio: float
    image_path: str


@dataclass(frozen=True)
class ExportSummary:
    total: int
    exported: int
    failed: int
    output_dir: str
