# No-text copies of the real-page results

The paper's cited aggregate numbers can be checked without distributing source
document text. Run from the repository root:

```sh
python3 research/realworld_e1_eval/results/notext_checks/prepare_notext_release.py --check-only
```

`SUMMARY_CHECKS.md` and `summary_checks.json` give the resulting numbers and
comparisons at the cited precision. No mismatch was found. This is a numerical
re-aggregation of saved per-token/per-target measurements, not a fresh experiment
on the original documents.

The original result files are never edited. The previously flagged 35 files are
excluded from distribution and replaced alongside by `_notext.csv` copies.
`notext_plan.json` lists the inputs. `notext_manifest.json` gives source/copy hashes,
row counts and conversion methods. CSV source-text fields become two columns:
`<field>_sha256` (SHA-256 of the UTF-8 string, with no normalization) and
`<field>_char_length` (Unicode code points). Even numeric-looking document text is
hashed. Empty text has the empty-string hash and length zero. Missing numeric
cells remain empty; no values are imputed. Every other parsed CSV cell, including
every numeric cell, is compared exhaustively with the original and preserved.
Categorical experiment labels, font metadata and opaque record/page identifiers
are retained so that numerical rows can still be filtered and grouped.

Flagged JSON reports are flattened into JSON-pointer/value rows. Every numeric
lexeme is preserved; string values are replaced with hashes and character counts.
Boolean and null leaves retain their types. Previously flagged Markdown reports
are represented by one hashed line per CSV row, including line terminators; their
prose and any quoted page text are not redistributed. Reports that contain no
source document text remain in their original form. The five approved PNGs under
`research/realworld_validation/figures/` contain numerical plots and a fictional
court page rendered by the local script, with no third-party page imagery.

SHA-256 here records equality without distributing the text. It is not a claim
that short names or other low-entropy strings cannot be guessed from a hash.

## What still needs the original text

Existing research scripts have not been changed to consume the distribution
schema or filenames. Full experimental reproduction requires obtaining the
datasets independently and rerunning those scripts to regenerate local originals.

- `research/realworld_e1_eval/run_eval.py` and `run_generic_attacker.py` need original text for
  surname-list matching, likely-name selection and truth/candidate geometry.
- `results/font_consistency/run_analysis.py` reads the original generic-attacker token list and
  source text to join tokens to source cells/entities and determine neighbours.
  `run_attacker.py` needs original surnames for Census indices, rendering and
  calibration. `validate_and_report.py` checks original identities/receipts and
  original file paths. Their full checks cannot run on hashes alone.
- `research/doclaynet_validation/run_experiment.py` needs source pages/OCR for
  verification and actual strings for rendering. `reporting.py` expects its
  original in-memory/result schema and original report/checksum filenames.
- `research/funsd_validation/run_funsd_validation.py` and `funsd_real.py` use
  original annotations/answer strings for exclusion checks, training candidates,
  length/width fitting, rendering and truth ranking.
- `verify_funsd_independent.py`, `make_funsd_figures.py` and
  `write_funsd_reports.py` expect the original result filenames and text columns;
  the independent verifier also rereads raw annotations and page images.
- The saved-output test in `tests/test_funsd_validation.py` looks for
  `out/scores.csv` and skips that artifact check when originals are absent. Its
  synthetic fixture tests remain available.

Thus the cited means/proportions are reproducible from the no-text files using
the new packaging check, but rerendering, reranking, inspecting quoted examples,
and the unchanged original end-to-end verifiers require the independently
obtained text/data. `research/realworld_validation/run_all.sh` is the separate
synthetic-document workflow and is unchanged.

## Distribution exclusions

Page images, raw DocLayNet/FUNSD annotations and archives, local environments,
downloaded fonts, build products, binary geometry caches and the 1,200 regenerated
synthetic PDFs are excluded. The reviewed unrelated local research/manuscript
work is also ignored. The manuscript figure script and source CSV are included;
its generated PDF/PNG/contact-sheet outputs are excluded. Archived historical
checksum/configuration files still describe the original experiments; consult
`notext_manifest.json` for distribution-copy checksums.
