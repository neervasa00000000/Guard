# E1 release fixes

## Candidate lists

The builders are `dict_emails`, `census` and `dict_words` in [e1lib.py](research/e1/scripts/e1lib.py).

- **E-mail local parts.** Take the first 1,000 alphabetic surnames from the 2010 U.S. Census surname CSV in file order and lowercase them. Use either `surname` or `initial.surname`, for each of the 26 lowercase ASCII initials. The initials are enumerated, with no given-name list. The only local-part separator added is a period after the initial. No digits are added. The `@` separates the local part from the domain.
- **Domains.** The weights are `gmail.com` 45%, `outlook.com` 20%, `yahoo.com` 15%, `hotmail.com` 10% and `icloud.com` 10%.
- **Size and prior.** Running the builder on the hash-verified Census CSV yields **135,000 distinct strings** and **15.6068118262 bits** of prior entropy. Each string's weight is the surname's Census count divided by the sum of counts for the selected surnames, times the local-part weight, times the domain weight. The bare surname receives 25% of the local-part mass and each initial receives 75% / 26.
- **Words.** With wordfreq 3.1.1, call `top_n_list("en", 60000)`, retain entries for which both `isalpha()` and `isascii()` are true, then take the first 20,000 in rank order. The prior is proportional to `word_frequency(word, "en")`. Running the builder gave 20,000 distinct entries.

## Clean-table correction

[rebuild_clean_summary.py](scripts/rebuild_clean_summary.py) reads the archived per-target A2 rows and the leading-zero digit rerun. It uses exact-likelihood scores in zero-tolerance cells and the archived feasible-set scores in the calibrated digit cells. It pools per-target scores, subtracts the mean residual entropy from the dictionary prior entropy, and computes 95% intervals using 10,000 font-cluster bootstrap draws with seed 20261101. The prior summary supplies the A1 values and area figures and remains available as [pooled_clean_feasible_set.csv](results/paper/e1/pooled_clean_feasible_set.csv).

The [corrected summary](results/paper/e1/pooled_clean_dict_grid_attacker.csv) is the input to `regenerate_tables.py`. Surnames at 16 px under A2 regenerate to **12.2% top-10 and 1.54 bits**, matching the printed clean table (Table II in the v6.1 PDF).

## Harness and per-target coverage

The [harness README](research/e1/README.md) documents the offline table check, Linux renderer setup and full CPU rerun. The released [case archives](research/e1/cases/) contain **25 gzip files** with **3,408,000 data records** including target manifests and alternative scores on shared targets. The largest file is **6,042,780 bytes**. The kit omitted the complete original main per-target directory. The archive includes the original raw results for four units and the clean A2 rescore for the full sweep. `scripts/rerun_full.sh` regenerates the raw A1/A2 and original A3 experiment, subject to the documented renderer inputs. A complete fresh render was outside the verification run.

## The 19 policy–condition cells

Here “exact” is the 1-px grid. The following matrix enumerates the cells from `e1_run.py`.

| Condition | Policy | Grid settings (px) | Cells |
|---|---|---|---:|
| Clean | Exact and square grid | 1, 8, 16, 32, 64 | 5 |
| JPEG quality 75 | Exact and square grid | 1, 8, 16, 32, 64 | 5 |
| Scan-like | Exact and square grid | 1, 8, 16, 32, 64 | 5 |
| Clean | Jitter 0–16 px per side, then snap | 1, 16 | 2 |
| Clean | Edge-aligned 128-px width class, full-line height, then snap | 1, 16 | 2 |

The 99 units are 90 from five lists × six fonts × three sizes (12, 16, 24 px), plus nine at 42 px from surnames, words and e-mails × DejaVu Sans, Liberation Sans and Liberation Serif. At 2,000 targets per unit, the 19 cells give **3,762,000 redactions**. Scoring A1 and A2 and adding the **128,000 A3 rows** gives **7,652,000 result rows**. No-box baselines are outside the redaction count.

## Verification

In a fresh Python 3.13.2 virtual environment with the root requirements installed, `pytest -q` passed and `bash scripts/reproduce.sh` exited successfully. The latter also prints the historical audit, including its unrelated open findings and the superseded feasible-set comparison.
