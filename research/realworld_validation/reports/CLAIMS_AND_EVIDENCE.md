# Claims and evidence

Each claim is a statement this run supports. The check is `src/verify_results.py` unless a row says otherwise.

| Claim | Result | File |
| --- | --- | --- |
| 1,200 pages, 0 sanitizer failures | 1200 pages, 0 failures | `results/statistics.json`, `results/documents.csv` |
| Glyph box matches the catalog | max edge error 0.000107 px | `results/verification.json` |
| Text was removed and the file reopened | 800 redactions, both extractors clean | `results/documents.csv` column `text_check` |
| Matched exact top-10 above no-box | 87.0% vs 8.8%, Holm p 0.006 | `results/statistics.json` |
| Field box equals the prior | difference 0 on every test page, feasible set 1000 | `results/attacker_results.csv` |
| Start-128 lift not separated from zero after Holm | difference 2.9 percentage points, Holm p 0.188 | `results/statistics.json` |
| Singletons exist on the shipped list | Times exact 21, Arial exact 30, Arial square-64 1 | `results/worst_case_results.csv` |
| Only square-64 covers neighbors | other policies, 0 neighboring words | `results/utility_results.csv` |
| Held-out exact does not beat no-box | top-10 7.4%, truth inside on 7.4% | `results/attacker_results.csv` |
| A duplicate mask adds nothing | top-10 stays 85.5% | `results/repeated_releases.csv` |
| A second font shrinks the set | median feasible 15 to 2 | `results/repeated_releases.csv` |
| Simulated scan, not a physical scan | top-10 63.7%, tolerance 0.98 px | `results/statistics.json` key `scan` |
| Verifier agreed | 0 failures | `results/verification.json` |

The manuscript Table 3 rates are not claims of this run. They live in `out/tables/table3.csv`.
