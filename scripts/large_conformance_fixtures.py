# SPDX-License-Identifier: MIT
"""Write the large GRD2 conformance cases to a caller-supplied directory."""

import argparse
from pathlib import Path
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import grd


def create_large_fixtures(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'grd2-oversized.GRD').open('wb') as fixture:
        fixture.write(b'GRD2\n')
        block = b' ' * (1024 * 1024)
        for _ in range(33):
            fixture.write(block)

    width, height = 2496, 1662
    rgb = bytearray(width * height * 3)
    state = 123456789
    for offset in range(0, len(rgb), 3):
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        rgb[offset] = state & 0xFF
        rgb[offset + 1] = (state >> 8) & 0xFF
        rgb[offset + 2] = (state >> 16) & 0xFF

    # This public test seed matches the conformance trust registry.
    key = Ed25519PrivateKey.from_private_bytes(bytes([42]) * 32)
    image = Image.frombytes('RGB', (width, height), bytes(rgb))
    document = grd.seal(image, key, purpose='personal', label='Large 4MP Noise', version=2, visual=True)
    (directory / 'grd2-large-4mp-noise.GRD').write_bytes(grd.encode(document))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    create_large_fixtures(parser.parse_args().directory)
