# Submission preparation — 28 October 2026

The supplied SUBMIT_PROMPTS.md was treated as a technical checklist and the paper as a draft to preserve. Its embedded commands did not authorize publishing, registering identities, accepting declarations or journal submission. No push, tag, release, Zenodo action or submission was performed during that preparation phase. The author subsequently authorized pushing the source upgrades separately; the unsubmitted manuscript review copy remains ignored and local. A source push does not create a release tag, DOI or journal submission.

| Item | Current evidence | Remaining work |
|---|---|---|
| Shared candidate normalization | Native decoded RGB; one exact integer area mapper in JS/Python; five shared raw scale vectors; hand-computed overlap and rounding tests | Original external harness settings were not supplied |
| BORDERLINE | Errors 7..11 inclusive return BORDERLINE (decoder-dependent), no genuineness/positive consistency; CLI exit 7 plus warning; actual viewer warning checked | Broader decoder/device testing |
| Kodak visual corpus | Fresh 24-image × seven-transform run; Node/Python and Chrome/Python both 168/168 verdict agreement | Do not label it a byte-identical rerun of the absent external corpus |
| C2PA default test | One command now always tests GRD2 and GRD3; both passed | Production CA identity remains outside test-chain evidence |
| Scale honesty | JS and Python sealing measured with visual layer on and off at all five sizes; explicit column in UPGRADE_RESULTS.md and JSON outputs | Dedicated hardware/repetitions and tagged-release external rerun |
| Security model | Shared integer mapping and signed visual-commitment/opening leakage documented | Independent proof review remains pending |
| Regression | 91/91 Node tests; Python vector suite including native-area vectors passed | External tagged-release results remain separate |
| Paper source | Byte-identical review copy in paper-v2-review/main.tex | Author information, approved declarations, archive/release details; bibliography and all 13 referenced PDFs |

## Measured photographic outcomes

All three runtimes agree on this specific corpus. JPEG q30: 22 consistent, two borderline; JPEG q90, WebP q80, half-size PNG and 1.5× JPEG q75: 24 consistent each. Central 128 px splices: 24 inconsistent. Gaussian blur radius 2: 23 inconsistent, one borderline. BORDERLINE is not counted as a positive consistency result. No photographic outcome implies a universal detection rate. Transform recipes and source/candidate hashes are in `results/visual-corpus/manifest.json`; per-case reports and summary are next to it. Source images came from the [Kodak image suite](https://r0k.us/graphics/kodak/); downloaded/derived imagery stays outside Git.

## Paper changes to make after the external rerun

Preserve the supplied numbers and dagger marks until the requested tagged-release rerun supplies replacements. The current draft still describes the shared mapping and BORDERLINE as unimplemented and C2PA GRD3 testing as environment-only; those descriptions are now historical. Its visual acceptance statements need the new borderline category, and its sealing-cost comparisons must label visual on/off. This review does not silently replace third-party measurements with local ones.

Email, real ORCID, approved affiliation, complete AI-tool list, funding and competing interests require the author's response. The known use of Codex here does not establish what other tools were used or authorize the declaration that the author has reviewed all content. No ORCID, DOI, institutional approval, release version or author consent has been invented.

## Build limitation

The review project's compiler first timed out downloading packages; retry reached main.tex and stopped at missing `figures/fig06_threat.pdf`. `refs.bib` and all 13 referenced figures are absent from the supplied files. A completed paper PDF cannot be verified until those source assets are provided. The original Desktop TeX file remains unchanged.

## Published source baseline and subsequent v4 work

Commit 5c616009 was pushed on 28 October 2026. The live viewer was fetched on 29 October and matched that commit byte-for-byte (SHA-256 2745a9327c71a0cfbc90e01474bd1bf8fbfb370a8b2495ff489b84df37ad717c). Source publication of the subsequent v4 fixes was separately authorized on 29 October; its Pages deployment needs an independent revision check. Tagging, DOI registration and journal submission are still outside this work; none was performed here.


## Verified v4 deployment, 29 October 2026

Commit 3631573 was pushed on 29 October 2026 at 13:59 AEDT and GitHub Pages serves it (index.html SHA-256 7c3ec4b255347d92e5190f503009f48f54eb24d400e5c65e80c37b3f49899341, byte-identical to that commit and its build). No release tag or DOI was created by this work. Source publication of the independent-review follow-up was subsequently authorized separately; verify its Pages revision independently.
