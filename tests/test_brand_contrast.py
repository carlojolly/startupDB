"""Keep the dark dashboard's small text and yellow controls readable."""
import pathlib
import re

import pytest

CSS = (pathlib.Path(__file__).resolve().parents[1] / "web/app/globals.css").read_text()
COLORS = dict(re.findall(r"--color-([\w-]+): #([0-9a-f]{6});", CSS))


def luminance(token):
    color = COLORS[token]
    channels = [int(color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


@pytest.mark.parametrize("foreground,background", [
    ("ink", "page"), ("ink-muted", "surface"), ("ink-faint", "surface"),
    ("on-navy-muted", "panel"), ("on-navy-faint", "navy"),
    ("navy", "brand"), ("brand", "brand-wash"), ("amber", "amber-wash"),
])
def test_small_text_meets_wcag_aa(foreground, background):
    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    assert (light + 0.05) / (dark + 0.05) >= 4.5
