"""Shared TileSeal geometry vectors and the real CLI padding path."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import grd
from grd_geometry import pad_box


class PaddingTests(unittest.TestCase):
    def test_shared_vectors(self):
        vectors = json.loads((ROOT / "tests/vectors/padding-vectors.json").read_text())
        for case in vectors:
            with self.subTest(case=case["name"]):
                img_w, img_h = case["image"]
                result = pad_box(tuple(case["box"].values()), grid=case["grid"],
                                 img_w=img_w, img_h=img_h, line_height=case["lineHeight"],
                                 width_class=case.get("widthClass", 128))
                self.assertEqual(result, tuple(case["expected"].values()))

    def test_padding_contains_selection_and_preserves_grid(self):
        import random
        rng = random.Random(4109)
        for i in range(3000):
            img_w, img_h = rng.randint(1, 512), rng.randint(1, 333)
            x, y = rng.randrange(img_w), rng.randrange(img_h)
            w, h = rng.randint(1, img_w-x), rng.randint(1, img_h-y)
            grid = (8, 16, 32, 64)[i % 4]
            px, py, pw, ph = pad_box((x,y,w,h), grid=grid, img_w=img_w, img_h=img_h)
            self.assertTrue(0 <= px <= x < x+w <= px+pw <= img_w)
            self.assertTrue(0 <= py <= y < y+h <= py+ph <= img_h)
            self.assertEqual((px % grid, py % grid), (0, 0))
            self.assertTrue(px+pw == img_w or (px+pw) % grid == 0)
            self.assertTrue(py+ph == img_h or (py+ph) % grid == 0)

    def test_cli_pad_boxes_preserves_signature_and_zeros_tiles(self):
        key = grd.Ed25519PrivateKey.generate()
        doc = grd.seal(Image.new("RGB", (384, 128), "white"), key, purpose="demo",
                       sub_tile=16, visual=False)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.GRD"
            source.write_bytes(grd.encode(doc))
            for padded in (False, True):
                output = Path(tmp) / f"redacted-{padded}.GRD"
                args = [sys.executable, str(ROOT / "grd.py"), "redact", str(source),
                        "--rect", "73,51,19,8", "--granularity", "16", "-o", str(output)]
                if padded:
                    args += ["--pad-boxes", "--line-height", "48"]
                run = subprocess.run(args, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr or run.stdout)
                report = grd.verify_v2(output.read_bytes(), include_pixels=True)
                self.assertTrue(report["regionVerified"])
                self.assertTrue(report["hiddenPixelsCleared"])
                self.assertEqual(report["_document"]["signature"], doc["signature"])
                area = sum(b["width"] * b["height"] for b in report["redactionMap"])
                self.assertEqual(area, 128 * 48 if padded else 32 * 16)


if __name__ == "__main__":
    unittest.main()
