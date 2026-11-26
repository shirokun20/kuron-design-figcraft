"""Text-size estimation helper used by the layout engine."""
import unittest


def estimate_text_size(text, font_size, font_family="Inter"):
    # Ratios mirror figcraft_tool.estimate_text_width: engine glyph metrics
    # measured monospace at ~0.54 * size and sans-serif at ~0.42 * size.
    if "Mono" in font_family:
        width = len(text) * font_size * 0.54
    elif "Space" in font_family or "Grotesk" in font_family:
        width = len(text) * font_size * 0.58 + 2
    else:
        width = len(text) * font_size * 0.42 + 2
    height = font_size * 1.3
    return round(width, 1), round(height, 1)


class LayoutEngineTests(unittest.TestCase):
    def test_mono_width_is_constant_ratio(self):
        width, height = estimate_text_size("123456", 10.0, "JetBrains Mono")
        self.assertAlmostEqual(width, 6 * 10.0 * 0.54, places=1)
        self.assertAlmostEqual(height, 13.0, places=1)

    def test_display_font_has_leading_constant(self):
        width, _ = estimate_text_size("AB", 20.0, "Space Grotesk")
        self.assertAlmostEqual(width, 2 * 20.0 * 0.58 + 2, places=1)

    def test_default_body_estimate(self):
        width, _ = estimate_text_size("Hello", 12.0)
        self.assertAlmostEqual(width, 5 * 12.0 * 0.42 + 2, places=1)


if __name__ == "__main__":
    unittest.main()
