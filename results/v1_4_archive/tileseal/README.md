# TileSeal 392-redaction rerun

The existing validator was rerun for its original 100 seeded image attempts, with the same six pinned fonts. Two out-of-page attempts are skipped, leaving 98 images × four grids = 392 redactions. All case IDs, target hashes and box coordinates match the original per-redaction archive recovered read-only from commit 733d48a. All 392 predicted and actual sealed tile sets match.

TileSeal f8f2558 was checked out separately and made read-only; its checkout remained clean. Output-only instrumentation hashes targets and records actual redaction-map cells; no calculation was changed. The signing key exists only in memory and is discarded. No images, names, private keys or raw dataset files are distributed. Run and renderer details are in config.json.
