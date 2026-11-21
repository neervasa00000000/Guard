# Area/OCR evaluation: prerequisite check only

No area/concealment/OCR performance table was generated. See config.json for blockers. The existing DocLayNet cache contains layout blocks. Extra text cells may contain multiple words, and the old neighbour-word figures are labelled OCR proportional-split estimates. Those cannot be relabelled as exact ground-truth word rectangles for any-overlap or 50%-area measurements. Tesseract must also be available with a fixed version, mode and hashed language data before OCR runs.

preflight_targets.csv reuses the exact 954 saved insertion targets and contains only hashes/lengths for inserted text. preflight_pages.csv and preflight_summary.csv record local annotation availability. No source images, raw annotation JSONs or document text are copied into this folder.

Required to continue: individual ground-truth word boxes/text for the DocLayNet pages, and a usable local Tesseract installation/language model. Alternatively, a separately authorized proxy protocol must be explicitly labelled as such; it is not the requested ground-truth experiment.
