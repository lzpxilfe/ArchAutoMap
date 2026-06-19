from __future__ import annotations

import os

from .constants import STANDARD_SCALES

# target_occupancy_ratio의 기본값 – UI에서 config로 전달되므로 여기서는 참조용으로만 사용
TARGET_OCCUPANCY_RATIO = 0.60

# 표준 축척 목록의 최솟값/최댓값과 일치시킴
MIN_EXPORT_SCALE = STANDARD_SCALES[0]   # 500
MAX_EXPORT_SCALE = STANDARD_SCALES[-1]  # 50000


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


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


def round_to_standard_scale(scale: float, standard_scales: tuple[int, ...] = STANDARD_SCALES) -> int:
    """scale 이상인 가장 작은 표준 축척을 반환한다.
    표준 목록을 초과하면 그냥 반올림 값을 반환한다."""
    for std in standard_scales:
        if std >= scale:
            return std
    return int(round(scale))


def adjusted_scale_from_bbox(
    feature_width_m: float,
    feature_height_m: float,
    map_width_mm: float,
    map_height_mm: float,
    target_ratio: float = TARGET_OCCUPANCY_RATIO,
    minimum_scale: float = MIN_EXPORT_SCALE,
    maximum_scale: float = MAX_EXPORT_SCALE,
    use_standard_scales: bool = True,
    min_context_buffer_m: float = 0.0,
) -> int:
    """유적 bbox와 목표 점유율로부터 축척을 직접 계산한다.

    계산 공식 (점유율 기준):
        ideal_scale = feature_size_m * 1000 / (map_size_mm * target_ratio)

    min_context_buffer_m > 0 이면, 유적 bbox 외곽으로 최소 해당 거리만큼의
    지형 맥락이 도면에 담기도록 하는 축척도 함께 계산하여
    두 값 중 더 넓은(큰) 쪽을 채택한다.

    가로·세로 중 더 큰 쪽을 기준으로 하여 유적이 도면을 초과하지 않게 한다.
    """
    if map_width_mm <= 0 or map_height_mm <= 0 or target_ratio <= 0:
        return int(minimum_scale)
    if feature_width_m <= 0 or feature_height_m <= 0:
        return int(minimum_scale)

    # ── 점유율 기준 축척 ────────────────────────────────────────────
    scale_w = (feature_width_m * 1000.0) / (map_width_mm * target_ratio)
    scale_h = (feature_height_m * 1000.0) / (map_height_mm * target_ratio)
    ideal = max(scale_w, scale_h)

    # ── 최소 지형 맥락 거리 기준 축척 ─────────────────────────────
    # 지도가 보여주는 실제 지상 크기(가로/세로) 자체가 최소한 min_context_buffer_m 미터 이상이 되도록 보장한다.
    # 유적이 작아 과도하게 줌인되는 것을 방지하며, 유적이 이미 크면 이 조건은 자연스럽게 통과된다.
    if min_context_buffer_m > 0:
        buffer_scale_w = (min_context_buffer_m * 1000.0) / map_width_mm
        buffer_scale_h = (min_context_buffer_m * 1000.0) / map_height_mm
        buffer_scale = max(buffer_scale_w, buffer_scale_h)
        ideal = max(ideal, buffer_scale)

    clamped = clamp(ideal, minimum_scale, maximum_scale)
    if use_standard_scales:
        return round_to_standard_scale(clamped, STANDARD_SCALES)
    return int(round(clamped))


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
