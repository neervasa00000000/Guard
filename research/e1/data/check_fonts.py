#!/usr/bin/env python3
"""Check local font files against fonts.json. This script does not download."""
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECEIPTS = json.loads((HERE / "fonts.json").read_text())


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    folder = Path(os.environ["E1_FONT_DIR"]) if os.environ.get("E1_FONT_DIR") else None
    failed = False
    for name, spec in RECEIPTS.items():
        path = Path(spec["path"])
        if folder is not None:
            path = folder / path.name
        expect = spec["sha256"]
        if path.is_file() and sha256(path) == expect:
            print(f"PASS\t{name}")
        else:
            failed = True
            print(f"FAIL\t{name}\texpected {expect}\tlooked at {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
