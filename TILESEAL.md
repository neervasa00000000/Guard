# TileSeal review and browser test plan

TileSeal (repository: Guard) is the browser companion to the IEEE Access draft on redaction geometry. The build produces a standalone [index.html](index.html) and its identical [grd_viewer.html](grd_viewer.html) alias.

## Browser checks

1. Run `npm run build` and `npm run dev`. Open `http://127.0.0.1:4195/#seal`. Choose a picture at least 384 × 192 px with a sample name on it. Drag around the name. Confirm the preview is black and the area readout updates.
2. Open **Add an area by numbers**. For a repeatable check, remove the dragged area and enter X 73, Y 51, Width 19 and Height 8. Set **Full text-line height** to 48 and leave rounding at 16 px. **Add area** should show 128 × 48 px and 6,144 px² with padding. Uncheck padding to see 32 × 16 px and 512 px². Re-enable padding and confirm the original padded size returns.
3. Review the preview, check the privacy acknowledgement and click **Seal and download .GRD**. Open it via **Check this file**. Expect **UNVERIFIED: SELF-SIGNED** and a retained-pixel match. **Download plain picture** should save a PNG with blacked-out pixels. Checking that PNG should say **NOT A GRD**.
4. Check a previously sealed GRD2 or GRD3. Confirm its existing verdict. Choose **Black out more areas**, add an area and download the copy. Open it and confirm the blackout. A file from a trusted signer should say **VERIFIED WITH REDACTIONS**. To exercise that verdict locally, run `node scripts/browser-fixtures.mjs --large`, then serve `/tmp/guard-qa` on localhost. In that QA viewer, use `genuine-v2.GRD` or `genuine-grd3-large.GRD`. The fixture viewer contains a temporary public test anchor.
5. In the same QA viewer, open `genuine-test.GRD` and confirm the GRD1 limitation message. Open `tampered-v2.GRD` and confirm that no picture or download action appears.

## Padding details

The editor defaults to a 32 px minimum line height. Set the field to the actual line height in the source image. TileSeal rounds selections outward, then expands to an inclusive 128 px width class and the requested line height. The expansion uses the nearest centred position permitted by the grid. At an edge it moves inward to cover the full selection. A partial edge tile may make the result slightly wider or taller than its target. An image narrower than the target uses its full width. The live total measures the union of the current boxes and compares it with the union of the original selections.

Padding coarsens the visible width. The width class, position and surrounding pixels can still convey information. New files seal with 16 px sub-tiles in 64 px parent tiles. A received file uses its original sub-tile size as a lower bound on rounding. A legacy whole-tile file uses 64 px.

The Python CLI exposes the same geometry through `--pad-boxes` and `--line-height`. Supply `--granularity 16` on a compatible file to match the browser default. Existing CLI calls retain their rounding-only behavior.

## Removed interface elements

- Advanced navigation, its back links, specialist disclosures and tab trust indicators.
- **Check a recompressed copy**, .grdp and candidate-image inputs, **Download visual proof**, **Check visual consistency**, its results and the whole-64-pixel visual-proof help.
- **Viewing options**, **Hold to reveal**, **Full view**, hide/show preview and window-away shield, reveal hint, per-session stamps and the related About text.
- **Your signer key**, signer name/password/confirmation, encrypted key chooser, create/unlock/lock controls, public contact download and signer status.
- **Trust a person** and its contact file, fingerprint confirmation, add/clear actions and status. **Load a trust bundle** and its bundle/root inputs, load/clear actions and status.
- **Technical report**, report download, the secondary technical-details disclosure and its check rows, issue lists, file size, hidden-area coordinates, timestamps and session/metadata sections.
- **Mark tiles**, its tile-selection overlay and separate export action. Received files now use the same rectangle editor.
- **Offline copy**, its viewer download, **Fit large photos**, **Also save the full original .GRD**, the signer shortcut, the 8 px rounding option, and the **More options** disclosure.
- Document-shape heuristic warning, cancel/clear controls, the separate **Check another file** button, and the sample-file launcher. The file chooser stays available above the verdict.
- About's example, long verdict and viewing explanations, limits and hosting panels. About retains the repository name and a short privacy note.

## Removed functions

Named functions retired from the browser controller:

- File and result helpers: `el`, `bytesLabel`, `disposeImage`, `reset`, `showFile`, `setStatus`, `renderResult`, `pairs`, `metadata`, `decode`, `mergedHiddenAreas`.
- Viewer and tile-selection code: `shield`, `setMode`, `showImage`, `overlay`, `draw`, `queueDraw`, `point`, `redactionGrid`, `gridBounds`, `gridHidden`, `gridForRect`, `positionTileOverlay`, `renderTileOverlay`, `setTileSelection`.
- Editor and navigation helpers superseded by the rectangle flow: `sealGrid`, `roundSealArea`, `drawSealEditor`, `renderSealAreas`, `addSealArea`, `prepareSealPreview`, `loadSealGrd`, `sealPoint`, `sealDraft`, `conversionStatus`, `syncSealConsent`, `showGuardView`, `workspaceMode`, `revealAdvancedTool`, `syncSealExtras`, `refreshSealSummary`, `canEditChecked`, `routeDroppedFile`.
- Session trust and signer actions: `sessionTrust`, `scheduleBundleExpiry`, `lockOfflineSigner`, `activateOfflineSigner`, `signerAction`.
- Anonymous callbacks for the removed copy, report, offline, viewing, tile selection, trust, signer and resize controls were removed with those features. The viewer's UI signer module was deleted.

The build no longer includes `mappedVisualTile`, `visualDecision`, `visualTile`, `exportProof`, `visualDecodeImage`, `verifyVisual`, or the old result-copy, trust-bundle and offline-signer modules. Their repository APIs and tests serve existing non-page workflows. The standalone page retains the shared sealing primitives and exact verification of legacy signed fields.
