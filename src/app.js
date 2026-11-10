// SPDX-License-Identifier: MIT
const $ = id => document.getElementById(id);
const sealCanvas = $("seal-canvas");
const checkCanvas = $("canvas");
const supportedGrids = [16, 32, 64];
let checkVersion = 0, editVersion = 0;
let checked = null, editor = null, savedFile = null;
let selections = [], dragStart = null, busy = false;
let activeMode = "seal";

function showMode(mode, updateHash = true) {
  activeMode = mode;
  $("convert-form").hidden = mode !== "seal";
  $("inspection-panel").hidden = mode !== "check";
  for (const [id, task] of [["tab-seal", "seal"], ["tab-verify", "check"]]) {
    if (task === mode) $(id).setAttribute("aria-current", "page");
    else $(id).removeAttribute("aria-current");
  }
  if (updateHash) history.replaceState(null, "", "#" + mode);
}

function readHash() {
  if (location.hash === "#about" || location.hash === "#privacy-details") {
    $("about").open = true;
    showMode(activeMode, false);
  } else if (location.hash !== "#workspace") {
    showMode(location.hash === "#check" ? "check" : "seal", false);
  }
}
window.addEventListener("hashchange", readHash);
readHash();

function setEditorStatus(message, error = false) {
  $("convert-status").textContent = message;
  $("convert-status").classList.toggle("error", error);
}

function download(contents, name, type) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function verifyFile(bytes, allowUnknownDisplay = false) {
  if (isGRD2(bytes)) return verifyGRD2(bytes);
  return createVerifier(TRUSTED, TRUST_POLICY, { allowUnknownDisplay })(bytes);
}

async function pictureBlob(report) {
  if (report.container) {
    // A legacy blur is valid as a disclosure but may still expose hidden pixels.
    const bytes = report.hiddenPixelsCleared === false
      ? await exportPlainImage(report.container) : containerImage(report.container);
    return new Blob([bytes], { type: "image/png" });
  }
  if (report.payload) return new Blob([report.payload], { type: report.meta.mime });
  throw new Error("The picture is unavailable.");
}

function paint(canvas, image, width, height) {
  const scale = Math.min(1, 1200 / Math.max(width, height));
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  canvas.style.width = `min(100%, ${canvas.width}px, ${65 * canvas.width / canvas.height}vh)`;
  const context = canvas.getContext("2d");
  context.fillStyle = image ? "#fff" : "#000";
  context.fillRect(0, 0, canvas.width, canvas.height);
  if (image) context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return context;
}

async function revealChecked(state, report) {
  let image;
  try {
    if (report.verdict !== "FULLY REDACTED")
      image = await createImageBitmap(await pictureBlob(report), { imageOrientation: "none" });
    if (state !== checked) return;
    const { width, height } = report.meta;
    if (image && (image.width !== width || image.height !== height))
      throw new Error("Decoded dimensions differ from the signed file.");
    paint(checkCanvas, image, width, height);
    state.displayReport = report;
    $("show-unknown").hidden = true;
    $("image-panel").hidden = false;
    $("redact-checked").hidden = !report.container || report.verdict === "FULLY REDACTED";
  } finally {
    image?.close();
  }
}

function renderCheck(report, file) {
  $("verdict-title").textContent = report.verdict;
  $("verdict-description").textContent = report.verdict === "FULLY REDACTED"
    ? "All areas are blacked out."
    : report.regionVerified
      ? report.redactionMap?.length
        ? "The retained pixels match the signature. Hidden areas are solid black."
        : "Every pixel matches the signature."
      : report.genuine ? "The whole picture matches the signature."
        : report.problems?.[0] ?? "The file could not be verified.";
  const trusted = report.signerStatus === "trusted" && !report.demo && !report.personal;
  $("verdict-signer").textContent = trusted && report.signerDisplayName
    ? "Trusted signer: " + report.signerDisplayName
    : report.signature_valid && ["self", "unknown", "demo"].includes(report.signerStatus)
      ? "Signer identity is unverified." : "";
  $("result").dataset.tone = trusted && (report.genuine || report.regionVerified) ? "good"
    : ["TAMPERED", "REVOKED KEY"].includes(report.verdict) ? "bad" : "caution";
  $("live-status").textContent = file.name;
  $("legacy-redaction-note").hidden = report.version !== 1 || !report.signature_valid;
  $("show-unknown").hidden = !report.canRevealUnknown;
  $("show-unknown").disabled = false;
  $("download-plain").disabled = false;
  $("result").hidden = false;
  $("verdict-title").focus();
}

async function openFile(file) {
  showMode("check");
  const version = ++checkVersion;
  checked = null;
  checkCanvas.width = checkCanvas.height = 1;
  $("result").hidden = $("image-panel").hidden = true;
  $("live-status").textContent = "Checking " + file.name + "…";
  try {
    const report = file.size > GRD3_LIMITS.bytes
      ? { verdict: "LIMIT EXCEEDED", problems: ["Choose a .GRD file up to 256 MiB."] }
      : await verifyFile(new Uint8Array(await file.arrayBuffer()));
    if (version !== checkVersion) return;
    const state = { file, report, displayReport: null };
    checked = state;
    renderCheck(report, file);
    if (report.viewable || report.genuine || (report.verdict === "FULLY REDACTED" && report.regionVerified)) {
      try {
        await revealChecked(state, report);
      } catch (error) {
        if (state !== checked) return;
        const unreadable = { verdict: "UNREADABLE", problems: [error.message] };
        state.report = unreadable;
        renderCheck(unreadable, file);
      }
    }
  } catch (error) {
    if (version !== checkVersion) return;
    $("live-status").textContent = "Could not open the picture. " + error.message;
  }
}

$("show-unknown").onclick = async () => {
  const state = checked;
  if (!state?.report.canRevealUnknown) return;
  $("show-unknown").disabled = true;
  try {
    const report = state.report.version === 1
      ? await verifyFile(new Uint8Array(await state.file.arrayBuffer()), true)
      : state.report;
    if (state !== checked || !report.canRevealUnknown) return;
    await revealChecked(state, report);
  } catch (error) {
    if (state === checked) $("live-status").textContent = error.message;
  } finally {
    if (state === checked) $("show-unknown").disabled = false;
  }
};

$("download-plain").onclick = async () => {
  const state = checked, report = state?.displayReport;
  if (!report) return;
  $("download-plain").disabled = true;
  try {
    let png;
    if (report.container) png = await exportPlainImage(report.container);
    else if (report.verdict === "FULLY REDACTED") {
      const { width, height } = report.meta;
      png = await encodeRgbPng(new Uint8Array(width * height * 3), width, height);
    } else {
      const image = await createImageBitmap(await pictureBlob(report), { imageOrientation: "none" });
      try {
        const surface = document.createElement("canvas");
        surface.width = image.width;
        surface.height = image.height;
        surface.getContext("2d").drawImage(image, 0, 0);
        png = await new Promise(resolve => surface.toBlob(resolve, "image/png"));
      } finally {
        image.close();
      }
    }
    if (!png) throw new Error("Could not create the PNG.");
    if (state === checked) download(png, "picture.png", "image/png");
  } catch (error) {
    if (state === checked) $("live-status").textContent = error.message;
  } finally {
    if (state === checked) $("download-plain").disabled = false;
  }
};

function setGrid(minimum, received) {
  const select = $("rounding");
  for (const option of select.options) option.disabled = Number(option.value) < minimum;
  select.value = String(supportedGrids.find(grid => grid >= minimum));
  $("grid-help").textContent = received
    ? `This file was sealed on a ${minimum}-pixel grid. Larger rounding only changes the blackout box.`
    : "Pictures are sealed on a 16-pixel grid. Choosing 32 or 64 px only makes this black-out box bigger; it does not change how the picture was sealed.";
}

function paddingOptions() {
  const enabled = $("pad-boxes").checked;
  const lineHeight = enabled ? $("line-height").valueAsNumber : 0;
  if (enabled && (!Number.isInteger(lineHeight) || lineHeight < 1 || lineHeight > 8192))
    throw new Error("Enter a full text-line height from 1 to 8,192 px.");
  return {
    grid: Number($("rounding").value), widthClass: enabled ? 128 : 0,
    lineHeight, imgW: editor.width, imgH: editor.height,
  };
}

function drawEditor(boxes, original) {
  const { preview, width, height } = editor;
  const context = sealCanvas.getContext("2d");
  context.drawImage(preview, 0, 0, sealCanvas.width, sealCanvas.height);
  context.fillStyle = "#000";
  const scaleX = sealCanvas.width / width, scaleY = sealCanvas.height / height;
  for (const box of boxes)
    context.fillRect(box.x * scaleX, box.y * scaleY, box.w * scaleX, box.h * scaleY);
  const area = boxUnionArea(boxes), selected = boxUnionArea(original);
  $("blackout-area").textContent = selected
    ? `Blacked-out area: ${area.toLocaleString()} px² (${(area / selected).toLocaleString(undefined, { maximumFractionDigits: 2 })}× what you selected)`
    : "Blacked-out area: 0 px²";
}

function invalidateReview() {
  $("convert-privacy").checked = false;
  $("check-sealed").hidden = true;
  savedFile = null;
}

function syncConsent() {
  $("convert-submit").disabled = busy || !editor || !editor.boxes
    || !$("convert-privacy").checked || (!!editor.doc && !selections.length);
}

function renderAreas(focusIndex = null) {
  if (!editor) return;
  $("line-height").disabled = !$("pad-boxes").checked;
  const list = $("seal-area-list");
  list.replaceChildren();
  try {
    const options = paddingOptions();
    editor.boxes = selections.map(box => padBox(box, options));
    drawEditor(editor.boxes, selections);
    for (const [index, box] of editor.boxes.entries()) {
      const item = document.createElement("li");
      item.textContent = `Area ${index + 1} · ${box.w} × ${box.h} px`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.setAttribute("aria-label", "Remove area " + (index + 1));
      remove.onclick = () => {
        if (busy) return;
        selections.splice(index, 1);
        invalidateReview();
        renderAreas(index);
      };
      item.append(remove);
      list.append(item);
    }
    $("redaction-status").textContent = `Areas round up to a ${options.grid}-pixel grid.`;
  } catch (error) {
    editor.boxes = null;
    // Keep the last valid blackout preview until the settings are corrected.
    $("redaction-status").textContent = error.message;
  }
  if (focusIndex !== null) {
    const buttons = list.querySelectorAll("button");
    (buttons[Math.min(focusIndex, buttons.length - 1)] ?? $("select-rectangle")).focus();
  }
  syncConsent();
}

function addArea(rect) {
  if (!editor || busy) return;
  try {
    if (selections.length >= 200) throw new Error("Use up to 200 blackout areas.");
    padBox(rect, paddingOptions());
    const { x, y, w, h } = rect;
    selections.push({ x, y, w: Math.min(w, editor.width - x), h: Math.min(h, editor.height - y) });
    invalidateReview();
    renderAreas();
  } catch (error) {
    $("redaction-status").textContent = error.message;
  }
}

function imagePoint(event) {
  const rect = sealCanvas.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(editor.width, (event.clientX - rect.left) * editor.width / rect.width)),
    y: Math.max(0, Math.min(editor.height, (event.clientY - rect.top) * editor.height / rect.height)),
  };
}

function dragBox(event) {
  const point = imagePoint(event);
  const x = Math.min(editor.width - 1, Math.floor(Math.min(point.x, dragStart.x)));
  const y = Math.min(editor.height - 1, Math.floor(Math.min(point.y, dragStart.y)));
  return { x, y, w: Math.max(1, Math.ceil(Math.max(point.x, dragStart.x)) - x),
    h: Math.max(1, Math.ceil(Math.max(point.y, dragStart.y)) - y) };
}

sealCanvas.addEventListener("pointerdown", event => {
  if (!editor?.boxes || busy || dragStart || event.button !== 0) return;
  dragStart = { ...imagePoint(event), pointerId: event.pointerId };
  sealCanvas.setPointerCapture(event.pointerId);
});
sealCanvas.addEventListener("pointermove", event => {
  if (!dragStart || dragStart.pointerId !== event.pointerId || !editor?.boxes || busy) return;
  const rect = dragBox(event);
  drawEditor([...editor.boxes, padBox(rect, paddingOptions())], [...selections, rect]);
});
sealCanvas.addEventListener("pointerup", event => {
  if (dragStart?.pointerId !== event.pointerId) return;
  const rect = dragBox(event);
  dragStart = null;
  addArea(rect);
  if (editor?.boxes) drawEditor(editor.boxes, selections);
});
for (const type of ["pointercancel", "lostpointercapture"]) sealCanvas.addEventListener(type, event => {
  if (dragStart?.pointerId !== event.pointerId) return;
  dragStart = null;
  if (editor?.boxes) drawEditor(editor.boxes, selections);
});

$("select-rectangle").onclick = () => {
  const [x, y, w, h] = ["rect-x", "rect-y", "rect-width", "rect-height"].map(id => $(id).valueAsNumber);
  addArea({ x, y, w, h });
};
for (const id of ["rounding", "pad-boxes", "line-height"]) $(id).addEventListener("input", () => {
  invalidateReview();
  renderAreas();
});
$("convert-privacy").onchange = syncConsent;

function loadEditor(image, file, doc) {
  const { width, height } = image;
  const preview = document.createElement("canvas");
  paint(preview, image, width, height);
  paint(sealCanvas, preview, width, height);
  editor = { width, height, preview, image, doc, boxes: [] };
  setGrid(doc ? doc.manifest.subTile ?? 64 : 16, !!doc);
  $("pad-boxes").checked = true;
  $("line-height").value = "32";
  $("finish-title").textContent = doc ? "Download the blacked-out copy" : "Seal and download";
  $("convert-submit").textContent = doc ? "Download blacked-out .GRD" : "Seal and download .GRD";
  $("seal-signer-summary").textContent = doc
    ? "The original signature stays with the file. You can black out more areas without its key."
    : "TileSeal creates a one-time key in this browser. The resulting file is self-signed.";
  $("convert-details").textContent = `${file.name} · ${width} × ${height} px`;
  $("seal-step-two").hidden = $("seal-step-three").hidden = false;
  renderAreas();
}

async function prepareSealInput(file, approvedState = null) {
  if (!file || busy) return;
  showMode("seal");
  const version = ++editVersion;
  editor?.image.close();
  editor = null;
  sealCanvas.width = sealCanvas.height = 1;
  selections = [];
  dragStart = null;
  savedFile = null;
  $("check-sealed").hidden = $("seal-step-two").hidden = $("seal-step-three").hidden = true;
  $("convert-privacy").checked = false;
  syncConsent();
  setEditorStatus("Opening " + file.name + "…");
  let image;
  try {
    if (file.size > GRD3_LIMITS.bytes) throw new Error("Choose a file up to 256 MiB.");
    if (approvedState) {
      if (approvedState !== checked || !approvedState.displayReport?.container) return;
      const report = approvedState.displayReport;
      image = await createImageBitmap(await pictureBlob(report), { imageOrientation: "none" });
      if (version !== editVersion || approvedState !== checked) return;
      if (image.width !== report.meta.width || image.height !== report.meta.height)
        throw new Error("Decoded dimensions differ from the signed file.");
      loadEditor(image, file, report.container);
    } else {
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (version !== editVersion) return;
      if (isGRD2(bytes) || /^GRD1$/.test(String.fromCharCode(...bytes.subarray(0, 4))) || /\.grd$/i.test(file.name)) {
        setEditorStatus("");
        await openFile(file);
        return;
      }
      const info = inspectConversionImage(bytes, { large: true });
      image = await createImageBitmap(new Blob([bytes], { type: info.mime }));
      if (version !== editVersion) return;
      const fitted = fitConversionDimensions(image.width, image.height, { large: true });
      if (fitted.width !== image.width || fitted.height !== image.height ||
          image.width * image.height !== info.width * info.height)
        throw new Error("Decoded dimensions exceed the image limits. Choose a smaller picture.");
      loadEditor(image, file, null);
    }
    image = null; // The editor now owns the bitmap.
    setEditorStatus(file.name + " is ready.");
  } catch (error) {
    if (version === editVersion) setEditorStatus(error.message, true);
  } finally {
    image?.close();
  }
}

async function buildSeal(source, grid) {
  let doc = source.doc;
  if (!doc) {
    const key = await crypto.subtle.generateKey("Ed25519", false, ["sign", "verify"]);
    const publicKey = new Uint8Array(await crypto.subtle.exportKey("raw", key.publicKey));
    const surface = document.createElement("canvas");
    surface.width = source.width;
    surface.height = source.height;
    const context = surface.getContext("2d", { willReadFrequently: true });
    context.drawImage(source.image, 0, 0);
    const rgba = new Uint8Array(context.getImageData(0, 0, source.width, source.height).data.buffer);
    doc = await sealRgba({
      rgba, width: source.width, height: source.height, publicKey, purpose: "personal",
      subTile: 16, visual: false, sign: bytes => crypto.subtle.sign("Ed25519", key.privateKey, bytes),
    });
  }

  const rects = source.boxes.map(({ x, y, w, h }) => ({ x, y, width: w, height: h }));
  if (!rects.length) return encodeGRD2(doc);
  if (doc.manifest.subTile) return redactRects(doc, rects, { granularity: grid });
  const indices = new Set(rects.flatMap(rect => tilesForRect(doc.manifest, rect)));
  return redactGRD2(doc, [...indices]);
}

$("convert-form").onsubmit = async event => {
  event.preventDefault();
  if ($("convert-submit").disabled || busy || !editor?.boxes || !$("convert-privacy").checked) return;
  const source = editor;
  busy = true;
  savedFile = null;
  dragStart = null;
  drawEditor(source.boxes, selections);
  $("check-sealed").hidden = true;
  $("convert-form").setAttribute("aria-busy", "true");
  $("blackout-controls").disabled = $("convert-input").disabled = $("convert-privacy").disabled = true;
  syncConsent();
  setEditorStatus("Preparing and checking your .GRD…");
  try {
    const bytes = await buildSeal(source, Number($("rounding").value));
    const report = await verifyGRD2(bytes);
    if (!report.regionVerified || !report.signature_valid || report.verdict === "REVOKED KEY" ||
        (source.boxes.length && report.hiddenPixelsCleared !== true))
      throw new Error("The file failed its own check. Nothing was downloaded.");
    savedFile = new File([bytes], "image.GRD", { type: "application/octet-stream" });
    download(bytes, savedFile.name, savedFile.type);
    setEditorStatus("Saved image.GRD.");
    $("check-sealed").hidden = false;
    if (activeMode === "seal") $("check-sealed").focus();
  } catch (error) {
    setEditorStatus(error.message, true);
  } finally {
    busy = false;
    $("blackout-controls").disabled = $("convert-input").disabled = $("convert-privacy").disabled = false;
    $("convert-form").removeAttribute("aria-busy");
    syncConsent();
  }
};

$("redact-checked").onclick = () => {
  const state = checked;
  if (!state?.displayReport?.container || state.displayReport.verdict === "FULLY REDACTED" || busy) return;
  $("convert-input").value = "";
  void prepareSealInput(state.file, state);
};
$("check-sealed").onclick = event => {
  event.preventDefault();
  if (savedFile) void openFile(savedFile);
};

for (const [id, handler] of [
  ["file-input", openFile],
  ["convert-input", prepareSealInput],
]) $(id).onchange = event => {
  const file = event.target.files[0];
  event.target.value = "";
  if (file) void handler(file);
};

window.addEventListener("dragover", event => {
  if (!event.dataTransfer?.types.includes("Files")) return;
  event.preventDefault();
  const upload = document.querySelector(activeMode === "seal" ? "#convert-form .upload" : "#inspection-panel .upload");
  upload.classList.add("over");
});
window.addEventListener("dragleave", event => {
  if (!event.relatedTarget) document.querySelectorAll(".upload.over").forEach(node => node.classList.remove("over"));
});
window.addEventListener("drop", event => {
  const file = event.dataTransfer?.files[0];
  if (!file) return;
  event.preventDefault();
  document.querySelectorAll(".upload.over").forEach(node => node.classList.remove("over"));
  if (/\.grd$/i.test(file.name) || (activeMode === "check" && !/^image\//.test(file.type)))
    void openFile(file);
  else void prepareSealInput(file);
});
