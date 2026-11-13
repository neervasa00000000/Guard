"""Regenerate the published candidate geometry tables and verify their metadata."""

import json
from multiprocessing import Pool
from pathlib import Path

from measure import table

if __name__ == "__main__":
    units = [(font, size) for font in ("DejaVuSans", "LiberationSerif") for size in (16, 24)]
    with Pool(4) as workers:
        result = workers.starmap(table, units)
    actual = [dict(font=f, size=s, pages=n, pdf_fonts=fonts) for f, s, n, fonts in result]
    assert actual == json.loads(Path("csv/tables_meta.json").read_text())["tables"]
    print("Candidate table metadata matches", actual)
