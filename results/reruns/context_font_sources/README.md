# Native context font inputs

The manifest records archive hashes, exact members, installed paths and member hashes for the added context-font families. Public archive URLs are recorded where downloaded in this run; the three preexisting Debian packages have unknown original URLs, explicitly recorded as null. Matching an embedded font identity is not evidence that a source document used this exact build. System fonts remain local dependencies and their hashes are recorded in the v4 config. No font binaries are distributed.

Run `python3 scripts/fetch_context_fonts.py --archive-dir PATH` with matching archives to restore the recorded members. The tool downloads only explicitly recorded public URLs when `--download` is supplied, verifies archive and member hashes, and writes only the named ignored font files. Missing original cached packages are reported, never substituted.
