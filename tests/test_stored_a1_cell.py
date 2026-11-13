"""Stored 200-target A1 comparison.

A fresh render of the published cell needs the census surname file.
Its SHA-256 was NOT FOUND, so this test checks the stored comparison
instead of rendering again.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORED = ROOT / "research/e1/mdpi_checks/posterior_toy/real_comparison.csv"


def test_stored_a1_exact_cell_has_200_matches():
    rows = [row for row in csv.DictReader(STORED.open())
            if row["attacker"] == "A1" and row["grid_px"] == "1"]
    assert len(rows) == 200
    assert all(row["match"] == "True" for row in rows)
