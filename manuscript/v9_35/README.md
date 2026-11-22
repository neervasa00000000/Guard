# Checks for the Journal of Cybersecurity and Privacy manuscript (v1.5-artifact)

v1.5-artifact adds three check scripts and this manuscript's number map to v1.4-artifact. No archived data changed.

| File | What it is |
|---|---|
| `research/e1/scripts/truth_kept.py` | Splits the exact-box scores of Table A13 by whether the true name was kept (Section 7.3). Reads `research/realworld_e1_eval/results/v4_fontmatched/per_token.csv.gz`. |
| `research/e1/scripts/field_overflow.py` | Counts the 50,000 surnames that a field box sized from the 1,000-name list would not cover (Section 8.2). Stops unless all 18 field widths match `research/e1/data/v1_2/field_widths.csv`. |
| `research/e1/scripts/margin_sensitivity.py` | Re-scores start-aligned padding with a 0-, 1- or 2-px box margin over all 50,000 surnames (Appendix B.2). Stops unless the 1-px rows match `research/e1/data/v1_3/tail_summary.csv`. |
| `manuscript/v9_35/expected_numbers.json` | The manuscript's numbers, each with its source, recomputed value and status (338 entries, 0 failures). |
| `manuscript/v9_35/EVIDENCE.md` | Maps each result to its script, archived input and status. |

The top-level `manuscript/expected_numbers.json` and `EVIDENCE.md` describe an earlier draft and are unchanged.

## Run

From the repository root. Each script writes one CSV to the current directory, so run it from `out/` (ignored by git):

```sh
mkdir -p out/v9_35 && cd out/v9_35
python ../../research/e1/scripts/truth_kept.py
E1_CENSUS=/path/to/Names_2010Census.csv python ../../research/e1/scripts/field_overflow.py
E1_CENSUS=/path/to/Names_2010Census.csv python ../../research/e1/scripts/margin_sensitivity.py
```

`truth_kept.py` needs pandas and reads only archived files. The other two re-render the six study fonts with `research/e1/e1lib.py` and `policies.py`. They need the full 2010 Census surname CSV (`scripts/fetch_data.py` downloads it to `data/census/Names_2010Census.csv`; SHA-256 checked) and the fonts named in `research/e1/data/fonts.json` (SHA-256 checked; set `E1_FONT_DIR` if they are elsewhere). Each takes about 30 seconds.

These checks were run with Python 3.13.5, Pillow 13.0.0 with Raqm, NumPy 2.5.5 and pandas 3.0.6. The study rendered with Pillow 12.3.0; the re-renders were accepted only because they reproduce the archived field widths and tail values exactly.
