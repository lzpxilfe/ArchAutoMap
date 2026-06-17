from __future__ import annotations

import json

from qgis.PyQt.QtCore import QSettings

from .constants import (
    DEFAULT_DPI,
    DEFAULT_FILL_COLOR_HEX,
    DEFAULT_OUTPUT_CRS_AUTHID,
    DEFAULT_OUTLINE_COLOR_HEX,
    DEFAULT_OUTLINE_WIDTH_MM,
    DEFAULT_TARGET_OCCUPANCY_RATIO,
    OUTPUT_MODE_FINAL_ONLY,
    SETTINGS_PREFIX,
)


class SettingsKey:
    BASE_LAYER_ID = "base_layer_id"
    FILL_LAYER_ID = "fill_layer_id"
    OUTLINE_LAYER_ID = "outline_layer_id"
    NAME_FIELD = "name_field"
    AREA_FIELD = "area_field"
    OUTPUT_CRS_AUTHID = "output_crs_authid"
    LAYOUT_MODE = "layout_mode"
    LAYOUT_NAME = "layout_name"
    MAP_ITEM_ID = "map_item_id"
    STYLE_ENABLED = "style_enabled"
    STYLE_ATTRIBUTE_ENABLED = "style_attribute_enabled"
    STYLE_ATTRIBUTE_FIELD = "style_attribute_field"
    STYLE_ATTRIBUTE_RULES = "style_attribute_rules"
    FILL_COLOR_HEX = "fill_color_hex"
    OUTLINE_COLOR_HEX = "outline_color_hex"
    OUTLINE_WIDTH_MM = "outline_width_mm"
    FEATURE_SEARCH = "feature_search"
    OUTPUT_MODE = "output_mode"
    OUTPUT_DIR = "output_dir"
    DPI = "dpi"
    TARGET_OCCUPANCY_RATIO = "target_occupancy_ratio"
    USE_STANDARD_SCALES = "use_standard_scales"


SETTINGS_DEFAULTS = {
    SettingsKey.OUTPUT_CRS_AUTHID: DEFAULT_OUTPUT_CRS_AUTHID,
    SettingsKey.FILL_COLOR_HEX: DEFAULT_FILL_COLOR_HEX,
    SettingsKey.OUTLINE_COLOR_HEX: DEFAULT_OUTLINE_COLOR_HEX,
    SettingsKey.OUTLINE_WIDTH_MM: DEFAULT_OUTLINE_WIDTH_MM,
    SettingsKey.OUTPUT_MODE: OUTPUT_MODE_FINAL_ONLY,
    SettingsKey.DPI: DEFAULT_DPI,
    SettingsKey.TARGET_OCCUPANCY_RATIO: DEFAULT_TARGET_OCCUPANCY_RATIO,
    SettingsKey.USE_STANDARD_SCALES: True,
    SettingsKey.STYLE_ATTRIBUTE_RULES: [],
}


class PluginSettings:
    PREFIX = SETTINGS_PREFIX

    def __init__(self):
        self._settings = QSettings()

    def get(self, key: str, default=None):
        if default is None:
            default = SETTINGS_DEFAULTS.get(key)
        return self._settings.value(f"{self.PREFIX}{key}", default)

    def set(self, key: str, value):
        self._settings.setValue(f"{self.PREFIX}{key}", value)

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, default))
        except (TypeError, ValueError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(key, default))
        except (TypeError, ValueError):
            return default

    def get_json(self, key: str, default=None):
        raw_value = self.get(key, None)
        if raw_value in (None, ""):
            return default

        if not isinstance(raw_value, str):
            return raw_value

        try:
            return json.loads(raw_value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return default

    def set_json(self, key: str, value):
        self.set(key, json.dumps(value, ensure_ascii=False))
