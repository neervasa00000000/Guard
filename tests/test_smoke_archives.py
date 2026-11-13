"""Smoke checks on the shipped inputs. No rendering and no downloads."""
import csv
import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_case_archive_count_and_one_open():
    sums = (ROOT / "research/e1/cases/SHA256SUMS").read_text().splitlines()
    assert len(sums) == 25
    name = sums[0].split()[1]
    with gzip.open(ROOT / "research/e1/cases" / name, "rt") as handle:
        header = handle.readline()
    assert "," in header


def test_census_head_is_first_thousand_alphabetic_names():
    with (ROOT / "research/e1/data/surnames_head1000.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1000
    assert rows[0]["name"] == "SMITH"
    assert all(row["name"].isalpha() for row in rows)


def test_e1lib_imports_and_email_head_is_one_thousand():
    import sys
    sys.path.insert(0, str(ROOT / "research" / "e1"))
    import e1lib
    names, counts = e1lib.census(1000)
    assert len(names) == 1000
    assert names[0] == "Smith"
    assert counts[0] > counts[-1]
