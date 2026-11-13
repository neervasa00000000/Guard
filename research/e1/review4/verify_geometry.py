"""Check the analytic likelihood against enumeration and rasterized Pillow text."""

import argparse
from collections import Counter
from itertools import product

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from geometry import Geometry, POLICIES, text_bounds


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("font", nargs="?")
    group.add_argument("--study-fonts", action="store_true")
    args = parser.parse_args()
    if args.study_fonts:
        import e1lib

        for name in e1lib.FONTS:
            verify(e1lib.font(name, 16))
    else:
        verify(ImageFont.truetype(args.font, 16))


def verify(font):
    strings = ("J", "j", "i", "Tj", "foo", "99", "a@example.com")
    pen, baseline = 32, 32
    for string in strings:
        mask = Image.new("L", (256, 64))
        ImageDraw.Draw(mask).text((pen, baseline), string, fill=255, font=font, anchor="ls")
        expected = tuple(edge - (pen if i % 2 == 0 else baseline)
                         for i, edge in enumerate(mask.getbbox()))
        assert text_bounds(font, string, "PIXEL-INK") == expected, string

    checks = 0
    for model in ("LAYOUT-BOX", "PIXEL-INK"):
        bounds = [text_bounds(font, string, model) for string in strings]
        ascent, descent = font.getmetrics()
        geometry = Geometry(bounds, -ascent, descent)
        for policy, y in product(POLICIES, (62, 63, 64, 65)):
            pens = range(54, 77)
            counts = [
                Counter(geometry.observe(policy, target, x, y) for x in pens)
                for target in range(len(strings))
            ]
            for observed in set().union(*counts):
                expected = [counts_by_box[observed] for counts_by_box in counts]
                np.testing.assert_array_equal(
                    geometry.counts(policy, observed, y, pens.start, pens.stop - 1), expected
                )
                for target, x in product(range(len(strings)), pens):
                    if geometry.observe(policy, target, x, y) != observed:
                        continue
                    one = [int(geometry.observe(policy, i, x, y) == observed)
                           for i in range(len(strings))]
                    np.testing.assert_array_equal(geometry.counts(policy, observed, y, x, x), one)
                    tight = geometry.observe(POLICIES[0], target, x, y)
                    assert observed[0] <= tight[0] <= tight[2] <= observed[2]
                    assert observed[1] <= tight[1] <= tight[3] <= observed[3]
                checks += 1
    print(f"{font.getname()}: passed {checks} observation likelihood checks "
          f"and {len(strings)} raster checks")


if __name__ == "__main__":
    main()
