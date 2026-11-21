# Remaining v1.4 prerequisite audit

This is an inventory, not an experimental rerun. No missing performance number is filled in. The anchor-margin experiment is complete at data/v1_5_anchor_margin; prior available-font and FUNSD-only OCR runs retain their documented limits.

The exact pinned Noto binary has been recovered and all six study-font hashes pass. Fresh rerender, TileSeal, email/digit and expanded font-context runs are now archived. The user supplied the v9.31 figure script; it is installed unchanged under manuscript/figures/. Historical failed-search records are preserved as search history, not a current missing-font claim.

The broader name-independent search hashed 2352 local TTF/OTF files in accessible roots, including renamed fonts, and found 0 pinned-hash matches. The earlier remote/local figure-script search is superseded by the user-supplied file.

| Item | Status | Reason |
|---|---|---|
| email_digits_sweep | complete | Fresh six-font sweep: 864000 target-policy rows, 432 summaries and 24 pooled rows; digit entropy remains explicitly unknown except constant-field zero. |
| noto_fresh_rerender | complete | Recovered exact pinned SHA-256; fresh 150000 full-list bounds match all three retained receipts, and 126000 target-policy scores reproduce v1.2. |
| mock_form_renderer_mismatch | not_run | Repository has replayed geometry/hit CSVs, but no original LibreOffice mock-form document/PDF/scan input set or end-to-end form generator. |
| rerender_188_and_2 | complete | Original generator recovered read-only from Git commit 733d48a; fresh six-font geometry and unchanged function reproduce 188/2000 and 2/2000, with hash-only per-target records. |
| tileseal_392 | complete | Original validator rerun with six pinned fonts and read-only f8f2558 checkout: 392/392 tile sets match; original target hashes and coordinates match historical per-redaction rows. |
| alternative_font_builds_36_cells | complete_new_sensitivity_run | Explicitly defined 6 fonts x 3 sizes x A1/A2, builds frozen before scoring: 2/36 cells shift +7.8 pp. Original build manifest remains unavailable; this does not verify historical build provenance. |
| v931_figure_script | complete | User-supplied script installed unchanged; five figures checked with pinned Source Sans Pro; 0 layout problems; 0 plotted values missing from CSV. |
| final_v14_release_check | blocked | Remaining experiment reproductions are incomplete; summary-number checks can cover only produced runs. Do not create v1.4-artifact. |

The original LibreOffice kit (kit.tar.gz, SHA-256 4c88f470e98c2865f84287713240652fb192cf4cc6db85ce4f8605ee03fb6bf5) is still missing. Accessible local archives, historical Git, Docker images/volumes and filename-only connected Drive searches did not supply its gen.py/measure.py/attack.py or original inputs. Existing per-form observations do not establish an end-to-end rerun. The user protocol requires reporting missing inputs, so no invented replacement run or final v1.4 tag is recorded. The new sensitivity run does not establish the lost historical alternative-build provenance. Nothing has been pushed.

Existing locked-manuscript baseline check in a clean local clone of 814545d3f6d4490956a2d7ac6123e5db9faf6a15: exit 0; SUMMARY	PASS 369	FAIL 0	EXPLORATORY 9. That earlier check covers the existing v9.4 expectations. The subsequent v931 figure and produced-summary checks are separate; the remaining experiment reproductions are still incomplete. See legacy_make_all.json and legacy_make_all.log.
