"""Download third-party inputs and check SHA-256.

Census CSV hash and Qwen weight hash were computed from the local copies
the study used. Gutenberg hashes are the study receipt. A file that does
not match is deleted. van Heusden page images are not downloaded.
"""
import hashlib
import ssl
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import certifi

ROOT = Path(__file__).resolve().parents[1]
GUTENBERG_DIR = ROOT / "data" / "gutenberg"
CENSUS_CSV = ROOT / "data" / "census" / "Names_2010Census.csv"
MODEL_FILE = ROOT / "data" / "models" / "Qwen2.5-0.5B" / "model.safetensors"

CENSUS_URL = "https://www2.census.gov/topics/genealogy/2010surnames/names.zip"
CENSUS_SHA = "6b4933178060b4e5ac8dd9a611ec15472d35eab98fe9027474bc5ccc5b7a8708"
MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-0.5B/resolve/main/model.safetensors"
MODEL_SHA = "88c142557820ccad55bb59756bfcfcf891de9cc6202816bd346445188a0ed342"

GUTENBERG = {
    11: "01b38ea4c710a84bc18d0bd41271a5a1a92b94e97b2812f4dece97d4a694725e",
    84: "2b97b7f8aad508649481d8dd4f6b54f9b965ddb3ba634e9151c815f537b49e42",
    98: "d54c2b80d40a40b982cd88852c6180bb944d95acdb028af3d0e01a1750681784",
    174: "38f36b510417177aa87a6a24c968e3ec63a447b7df36a9c1a7c5a3f2d9e51547",
    345: "96cd16eacdbfebae8fdda5591f66e0cc8ee76be18e0cd1aca02bc00615782d28",
    1342: "3f6bb9d6f78e0293b56acd4714dd68cb7d6d1d293402031ce9d5a216bcaf9d75",
    1661: "922e2a12ccb43a4c9544c260b2166c6ad2097aeb5957faeee113f173bb857cd0",
    2701: "b5e88b71a1cda068e9ab1d94344c9d932338ba6da1a66def97a1aecd9cfcc87d",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "black-box-redaction-fetch/1.0"})
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(request, context=context) as response, dest.open("wb") as out:
        while True:
            block = response.read(1 << 20)
            if not block:
                break
            out.write(block)


def fetch_checked(url, dest, expected, label):
    if dest.exists() and sha256(dest) == expected:
        print(f"MATCH {label}")
        return True
    try:
        download(url, dest)
    except OSError as exc:
        print(f"NOT FOUND {label} download failed: {exc}")
        return False
    got = sha256(dest)
    if got == expected:
        print(f"MATCH {label}")
        return True
    dest.unlink(missing_ok=True)
    print(f"MISMATCH {label} got {got}")
    return False


def fetch_census():
    if CENSUS_CSV.exists() and sha256(CENSUS_CSV) == CENSUS_SHA:
        print("MATCH Names_2010Census.csv")
        return True
    CENSUS_CSV.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "names.zip"
            download(CENSUS_URL, archive)
            with zipfile.ZipFile(archive) as zipped:
                member = next(
                    (name for name in zipped.namelist() if name.endswith("Names_2010Census.csv")),
                    None,
                )
                if member is None:
                    print("NOT FOUND Names_2010Census.csv inside names.zip")
                    return False
                CENSUS_CSV.write_bytes(zipped.read(member))
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"NOT FOUND Names_2010Census.csv download failed: {exc}")
        return False
    got = sha256(CENSUS_CSV)
    if got == CENSUS_SHA:
        print("MATCH Names_2010Census.csv")
        return True
    CENSUS_CSV.unlink(missing_ok=True)
    print(f"MISMATCH Names_2010Census.csv got {got}")
    return False


def main():
    print("VAN HEUSDEN PAGE IMAGES excluded")
    failed = not fetch_census()
    failed = not fetch_checked(MODEL_URL, MODEL_FILE, MODEL_SHA, "Qwen2.5-0.5B/model.safetensors") or failed
    GUTENBERG_DIR.mkdir(parents=True, exist_ok=True)
    for ebook, expected in GUTENBERG.items():
        dest = GUTENBERG_DIR / f"pg{ebook}.txt"
        url = f"https://www.gutenberg.org/cache/epub/{ebook}/pg{ebook}.txt"
        if not fetch_checked(url, dest, expected, f"pg{ebook}.txt"):
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
