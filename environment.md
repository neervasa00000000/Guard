# Environment

Recorded on the machine that produced this release branch.

- OS: macOS 27.2, arm64
- Python used for the product checks: 3.13.2
- Pillow 13.0.0 and cryptography 50.0.2 in the repository `.venv`
- The posterior check was run earlier with Pillow 12.3.0
- NumPy 2.5.4 and pandas 3.1.1 in `~/tileseal-t3-lm/venv`
- The paired-test run used that same NumPy and pandas
- torch 2.15.0 and transformers 5.22.2 are in that study environment and are not required for `scripts/reproduce.sh`
- RAQM in the product `.venv`: not available (`PIL.features.check('raqm')` is false)
- FreeType and FriBidi versions: NOT FOUND from this checkout
- LibreOffice: NOT FOUND on this machine
- Hardware: the development laptop used for the checks. A full CPU-only rerun is described in `scripts/rerun_full.sh`

`pad_box` at commit `eebdcfb` grows a box from its centre and uses a 32 px minimum height. That is the product function still in `grd_geometry.py`. It is not the paper's start-aligned policy. Product decision pending. The function was not changed.
