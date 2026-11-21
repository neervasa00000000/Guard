# Remaining v1.4 prerequisite audit

This is an inventory, not an experimental rerun. No missing performance number is filled in. The anchor-margin experiment is complete at data/v1_5_anchor_margin; prior available-font and FUNSD-only OCR runs retain their documented limits.

The pinned Noto binary was not found among accessible local candidates or six official current/historical builds. Searches were limited by macOS privacy denials in some folders. The user subsequently supplied the v9.31 figure script; it is installed unchanged under manuscript/figures/. Its current check status is recorded below.

The broader name-independent search hashed 2352 local TTF/OTF files in accessible roots, including renamed fonts, and found 0 pinned-hash matches. The earlier remote/local figure-script search is superseded by the user-supplied file.

| Item | Status | Reason |
|---|---|---|
| email_digits_sweep | blocked | Fresh six-font rendering requires pinned Noto Sans; surname geometry cannot substitute for email/digit geometry. |
| noto_fresh_rerender | blocked | No checked binary matches fonts.json; retained geometry is not a fresh render. |
| mock_form_renderer_mismatch | not_run | Repository has replayed geometry/hit CSVs, but no original LibreOffice mock-form document/PDF/scan input set or end-to-end form generator. |
| rerender_188_and_2 | not_run | Archived counts exist, but the mixed-font rerender generator, same-target mapping and per-render settings needed to rerun those specific 2000 targets are absent from released code. |
| tileseal_392 | blocked | e1_validate_guard.py requires all six pinned fonts via E.check_render_inputs; no replacement and no claimed 392-case rerun. |
| alternative_font_builds_36_cells | not_run | Original alternative-build manifest and 36-cell experiment harness are not in released code; do not choose different builds and label them a reproduction. |
| v931_figure_script | complete | User-supplied script installed unchanged; five figures checked with pinned Source Sans Pro; 0 layout problems; 0 plotted values missing from CSV. |
| final_v14_release_check | blocked | Remaining experiment reproductions are incomplete; summary-number checks can cover only produced runs. Do not create v1.4-artifact. |

The user protocol says to stop when prerequisites are unavailable. Fresh six-font email/digit and archive experiments have not been represented as completed. LibreOffice is installed, but its availability alone does not supply the missing original mock forms. No new tag or push is authorized by this audit.

Existing locked-manuscript baseline check in a clean local clone of 814545d3f6d4490956a2d7ac6123e5db9faf6a15: exit 0; SUMMARY	PASS 369	FAIL 0	EXPLORATORY 9. That earlier check covers the existing v9.4 expectations. The subsequent v931 figure and produced-summary checks are separate; the remaining experiment reproductions are still incomplete. See legacy_make_all.json and legacy_make_all.log.
