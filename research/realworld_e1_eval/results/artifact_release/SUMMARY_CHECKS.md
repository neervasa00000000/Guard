# Checks from no-text distribution copies

These calculations read numeric columns from the distributed no-text CSVs. They do not read any excluded original text, page images, raw annotations or dataset archives. Numerical field preservation is exhaustively checked during conversion.

| Metric | n usable | Recomputed | Cited | Match at cited precision |
|---|---:|---:|---:|---|
| DocLayNet v2 exact bits | 5311 | 0.0609267121045 | 0.061 | True |
| DocLayNet v2 exact top-10 percent | 5311 | 0.0376576915835 | 0.038 | True |
| FUNSD v2 exact bits | 760 | 0.00261446096809 | 0.0026 | True |
| DocLayNet line same-size percent | 2145 | 92.634032634 | 92.63 | True |
| DocLayNet line same-font percent | 4829 | 77.5729964796 | 77.57 | True |
| Font-matched attacker n | 66 | 66 | 66 | True |
| Font-matched attacker bits | 66 | 1.65554882204 | 1.66 | True |
| DocLayNet painted exact matched 16px bits | 954 | 6.93765133447 | 6.94 | True |
| Separate FUNSD length-width summary integrity | 585 | 1.16637619228 | 1.1663761923 | True |

The painted result is the 16px, exact-box, matched-template evaluation arm (954 targets). The two font-consistency percentages use line neighbours and exclude unknown comparisons. FUNSD v2 and the separate length-width experiment are distinct analyses.

Recheck without originals: `python3 research/realworld_e1_eval/results/artifact_release/prepare_notext_release.py --check-only`.
