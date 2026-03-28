from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StyleConfig:
    fill_color_hex: str
    outline_color_hex: str
    outline_width_mm: float


@dataclass(frozen=True)
class LayoutConfig:
    mode: str
    layout_name: str = ""
    map_item_id: str = ""
    page_width_mm: float = 105.0
    page_height_mm: float = 80.0


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
    dpi: int = 300
    output_mode: str = "final_only"
    output_dir: str = ""
    preview_dpi: int = 120


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
