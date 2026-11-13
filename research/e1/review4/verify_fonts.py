"""Verify supplied fonts against the study receipts and install exact container paths."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("extracted", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    expected = "e68e1928a60bb3e480bafcb7806af53ab90924888410257fa6414cdc1d3abf46"
    actual = digest(args.archive)
    print(f"Archive SHA-256 {actual}", flush=True)
    if actual != expected:
        raise SystemExit("Font archive SHA-256 mismatch")

    sums, = args.extracted.rglob("SHA256SUMS")
    subprocess.run(["shasum", "-a", "256", "-c", sums.name], cwd=sums.parent, check=True)

    verified = []
    for name, row in json.loads(args.manifest.read_text()).items():
        dest = Path(row["path"])
        matches = [path for path in args.extracted.rglob(dest.name)
                   if path.is_file() and digest(path) == row["sha256"]]
        if len(matches) != 1:
            raise SystemExit(f"Expected one exact file for {name}, found {len(matches)}")
        print(f"{name}: {row['sha256']} {matches[0]} -> {dest}", flush=True)
        verified.append((matches[0], dest))
    if args.install:
        for source, dest in verified:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)


if __name__ == "__main__":
    main()
