from __future__ import annotations

import os

TARGET_OCCUPANCY_RATIO = 0.60
MIN_EXPORT_SCALE = 3000
MAX_EXPORT_SCALE = 50000

SCALE_RULES = (
    (20000, 9000),
    (100000, 11000),
    (150000, 13000),
    (210000, 16000),
    (240000, 18000),
    (400000, 20000),
)
DEFAULT_LARGE_SCALE = 24000


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def scale_from_area(area_m2: float) -> int:
    try:
        numeric_area = float(area_m2)
    except (TypeError, ValueError):
        numeric_area = 0.0

    for threshold, scale in SCALE_RULES:
        if numeric_area < threshold:
            return scale
    return DEFAULT_LARGE_SCALE


def extent_dimensions_for_scale(
    scale: float,
    map_width_mm: float,
    map_height_mm: float,
) -> tuple[float, float]:
    width = (map_width_mm * scale) / 1000.0
    height = (map_height_mm * scale) / 1000.0
    return width, height


def occupancy_ratios(
    feature_width_m: float,
    feature_height_m: float,
    scale: float,
    map_width_mm: float,
    map_height_mm: float,
) -> tuple[float, float]:
    extent_width_m, extent_height_m = extent_dimensions_for_scale(
        scale=scale,
        map_width_mm=map_width_mm,
        map_height_mm=map_height_mm,
    )
    if extent_width_m <= 0 or extent_height_m <= 0:
        return 0.0, 0.0
    return feature_width_m / extent_width_m, feature_height_m / extent_height_m


def adjusted_scale_from_bbox(
    base_scale: float,
    feature_width_m: float,
    feature_height_m: float,
    map_width_mm: float,
    map_height_mm: float,
    target_ratio: float = TARGET_OCCUPANCY_RATIO,
    minimum_scale: float = MIN_EXPORT_SCALE,
    maximum_scale: float = MAX_EXPORT_SCALE,
) -> int:
    clamped_base = clamp(base_scale, minimum_scale, maximum_scale)
    width_ratio, height_ratio = occupancy_ratios(
        feature_width_m=feature_width_m,
        feature_height_m=feature_height_m,
        scale=clamped_base,
        map_width_mm=map_width_mm,
        map_height_mm=map_height_mm,
    )
    current_ratio = max(width_ratio, height_ratio)
    if current_ratio <= 0:
        return int(round(clamped_base))

    adjusted = clamped_base * (current_ratio / target_ratio)
    return int(round(clamp(adjusted, minimum_scale, maximum_scale)))


def occupancy_status(occupancy_ratio: float) -> str:
    if occupancy_ratio < 0.40:
        return "작음"
    if occupancy_ratio <= 0.75:
        return "적정"
    return "큼"


def circle_ratio(width_ratio: float, height_ratio: float) -> float:
    return clamp(max(width_ratio, height_ratio), 0.05, 0.98)


def resolve_fill_color(
    default_fill_color_hex: str,
    attribute_value,
    attribute_rules: tuple[tuple[str, str], ...] | list[tuple[str, str]] | None = None,
) -> str:
    normalized_value = "" if attribute_value in (None, "") else str(attribute_value).strip()
    for rule_value, fill_color_hex in attribute_rules or ():
        if normalized_value == str(rule_value).strip():
            return fill_color_hex
    return default_fill_color_hex


def sanitize_filename(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in (" ", "_", "-") else "_"
        for character in str(value).strip()
    ).strip()
    return cleaned or "feature"


def unique_output_path(
    output_dir: str,
    stem: str,
    suffix: str,
    used_paths: set[str] | None = None,
) -> str:
    used_paths = used_paths if used_paths is not None else set()
    safe_stem = sanitize_filename(stem)
    candidate_name = f"{safe_stem}{suffix}"
    candidate_path = os.path.join(output_dir, candidate_name)
    counter = 1

    while candidate_path.lower() in used_paths or os.path.exists(candidate_path):
        candidate_name = f"{safe_stem}_{counter:03d}{suffix}"
        candidate_path = os.path.join(output_dir, candidate_name)
        counter += 1

    used_paths.add(candidate_path.lower())
    return candidate_path
