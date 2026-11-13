"""Release checks for seal, redact, verify, and grid snapping."""
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import grd
from grd_geometry import _snap_axis


def _pem(key):
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def test_grid_snap_matches_floor_ceil():
    for grid in (8, 16, 32, 64):
        left, right = _snap_axis(10, 30, 400, grid)
        assert left == math.floor(10 / grid) * grid
        assert right == math.ceil(40 / grid) * grid


def test_redact_sign_verify_and_one_pixel():
    key_path = None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            key_path = folder / "demo-key.pem"
            image = folder / "page.png"
            Image.new("RGB", (128, 128), "white").save(image)
            sealed = folder / "page.GRD"
            redacted = folder / "redacted.GRD"
            key = Ed25519PrivateKey.generate()
            key_path.write_bytes(_pem(key))
            sealed.write_bytes(grd.encode(grd.seal(
                Image.new("RGB", (128, 128), "white"), key,
                purpose="demo", visual=False, sub_tile=16)))
            report = grd.verify_v2(sealed.read_bytes())
            assert report["verdict"] == "DEMO"
            assert report["signature_valid"] is True
            cli = subprocess.run(
                [sys.executable, "-m", "tileseal", "seal", str(image),
                 "--key", str(key_path), "--no-visual", "-o", str(folder / "cli.GRD")],
                cwd=ROOT, capture_output=True, text=True)
            assert cli.returncode == 0, cli.stderr
            cli_report = grd.verify_v2((folder / "cli.GRD").read_bytes())
            assert cli_report["signature_valid"] is True
            redact = subprocess.run(
                [sys.executable, "-m", "tileseal", "redact", str(sealed),
                 "--rect", "8,8,20,12", "--granularity", "16", "-o", str(redacted)],
                cwd=ROOT, capture_output=True, text=True)
            assert redact.returncode == 0, redact.stderr
            redacted_report = grd.verify_v2(redacted.read_bytes())
            assert redacted_report["verdict"] == "DEMO"
            assert redacted_report["regionVerified"] is True
            doc = json.loads(sealed.read_bytes()[5:])
            rgb, width, height = grd.png_read(grd.un64(doc["image"]))
            changed = bytearray(rgb)
            changed[0] ^= 0xFF
            doc["image"] = grd.b64(grd.png_write(bytes(changed), width, height))
            tampered = grd.verify_v2(grd.encode(doc))
            assert tampered["verdict"] == "TAMPERED"
            key_path.unlink()
            assert not key_path.exists()
    finally:
        if key_path is not None and key_path.exists():
            key_path.unlink()
