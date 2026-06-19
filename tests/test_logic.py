import os
import tempfile
import unittest

from core.logic import (
    adjusted_scale_from_bbox,
    circle_ratio,
    occupancy_status,
    resolve_fill_color,
    round_to_standard_scale,
    sanitize_filename,
    unique_output_path,
)


class LogicTests(unittest.TestCase):
    def test_adjusted_scale_respects_target_ratio_and_clamp(self):
        # With standard scales disabled
        scale_raw = adjusted_scale_from_bbox(
            feature_width_m=320,
            feature_height_m=140,
            map_width_mm=105,
            map_height_mm=80,
            use_standard_scales=False,
        )
        self.assertEqual(scale_raw, 5079)

        # With standard scales enabled (rounds 5079 up to 6000)
        scale_std = adjusted_scale_from_bbox(
            feature_width_m=320,
            feature_height_m=140,
            map_width_mm=105,
            map_height_mm=80,
            use_standard_scales=True,
        )
        self.assertEqual(scale_std, 6000)

        # Tiny scale without standard scales
        tiny_scale_raw = adjusted_scale_from_bbox(
            feature_width_m=40,
            feature_height_m=20,
            map_width_mm=105,
            map_height_mm=80,
            use_standard_scales=False,
        )
        self.assertEqual(tiny_scale_raw, 635)

        # Tiny scale with standard scales (rounds 635 up to 1000)
        tiny_scale_std = adjusted_scale_from_bbox(
            feature_width_m=40,
            feature_height_m=20,
            map_width_mm=105,
            map_height_mm=80,
            use_standard_scales=True,
        )
        self.assertEqual(tiny_scale_std, 1000)

    def test_adjusted_scale_respects_min_context_buffer(self):
        # min_context_buffer_m = 1000m (minimum map extent is 1000m)
        # buffer_scale_w = 1000 * 1000 / 105 = 9523.8
        # buffer_scale_h = 1000 * 1000 / 80 = 12500
        # ideal scale = 12500
        scale_raw_buffered = adjusted_scale_from_bbox(
            feature_width_m=40,
            feature_height_m=20,
            map_width_mm=105,
            map_height_mm=80,
            use_standard_scales=False,
            min_context_buffer_m=1000.0,
        )
        self.assertEqual(scale_raw_buffered, 12500)

        # With standard scales enabled, 12500 rounds up to 15000
        scale_std_buffered = adjusted_scale_from_bbox(
            feature_width_m=40,
            feature_height_m=20,
            map_width_mm=105,
            map_height_mm=80,
            use_standard_scales=True,
            min_context_buffer_m=1000.0,
        )
        self.assertEqual(scale_std_buffered, 15000)

    def test_round_to_standard_scale(self):
        # standard_scales = (500, 600, 1000, 1200, 1500, 2000, 2500, 3000, 5000, 6000, 10000, 12000, 15000, 20000, 25000, 50000)
        self.assertEqual(round_to_standard_scale(450), 500)
        self.assertEqual(round_to_standard_scale(500), 500)
        self.assertEqual(round_to_standard_scale(550), 600)
        self.assertEqual(round_to_standard_scale(1201), 1500)
        self.assertEqual(round_to_standard_scale(45000), 50000)
        self.assertEqual(round_to_standard_scale(60000), 60000)

    def test_occupancy_status(self):
        self.assertEqual(occupancy_status(0.20), "작음")
        self.assertEqual(occupancy_status(0.60), "적정")
        self.assertEqual(occupancy_status(0.90), "큼")

    def test_circle_ratio_clamps(self):
        self.assertAlmostEqual(circle_ratio(0.01, 0.02), 0.05)
        self.assertAlmostEqual(circle_ratio(1.2, 0.8), 0.98)
        self.assertAlmostEqual(circle_ratio(0.44, 0.25), 0.44)

    def test_resolve_fill_color_prefers_matching_attribute_rule(self):
        rules = (("국보", "#AA3300"), ("사적", "#006699"))
        self.assertEqual(resolve_fill_color("#CCCCCC", "사적", rules), "#006699")
        self.assertEqual(resolve_fill_color("#CCCCCC", "보물", rules), "#CCCCCC")

    def test_sanitize_filename_preserves_letters_and_korean(self):
        self.assertEqual(sanitize_filename("유적:01/?"), "유적_01__")
        self.assertEqual(sanitize_filename("  "), "feature")

    def test_unique_output_path_adds_suffix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            used = set()
            first = unique_output_path(temp_dir, "sample", ".jpg", used)
            self.assertTrue(first.endswith(os.path.join(temp_dir, "sample.jpg")))

            second = unique_output_path(temp_dir, "sample", ".jpg", used)
            self.assertTrue(second.endswith(os.path.join(temp_dir, "sample_001.jpg")))


if __name__ == "__main__":
    unittest.main()
