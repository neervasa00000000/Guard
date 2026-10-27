// SPDX-License-Identifier: MIT
if (self !== top) {
  document.documentElement.classList.add("framed");
  const warning = document.createElement("p");
  warning.className = "frame-warning";
  warning.textContent =
    "Guard does not run inside embedded pages. Open the inspector directly to check a file.";
  const link = document.createElement("a");
  link.className = "frame-warning";
  link.textContent = "Open Guard";
  link.href = location.href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  document.body.replaceChildren(warning, link);
  return;
}
const $ = (id) => document.getElementById(id);
const ORIGINAL_HTML = "<!doctype html>\n" + document.documentElement.outerHTML;
const SESSION = hex(crypto.getRandomValues(new Uint8Array(8))).toUpperCase();
let currentContainer = null,
  redactionEditing = false,
  selectedTiles = new Set(),
  operation = 0,
  currentReport = null,
  bitmap = null,
  held = null,
  keyboardPoint = null,
  reveal = true,
  clock = null,
  drawQueued = false;
const canvas = $("canvas"),
  stage = $("stage");
const setStatus = (message) => {
  $("live-status").textContent = message;
};
function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (cls) node.className = cls;
  return node;
}
function bytesLabel(n) {
  return n < 1024
    ? n + " bytes"
    : n < 1024 * 1024
      ? (n / 1024).toFixed(1) + " KiB"
      : (n / 1024 / 1024).toFixed(1) + " MiB";
}
function disposeImage() {
  currentContainer = null;
  redactionEditing = false;
  selectedTiles.clear();
  $("tile-overlay").replaceChildren();
  $("tile-overlay").hidden = true;
  $("redaction-tools").hidden = true;
  $("legacy-redaction-note").hidden = true;
  $("redact-mode").setAttribute("aria-pressed", "false");
  $("redact-mode").textContent = "Mark tiles";
  $("export-redacted").disabled = true;
  clearInterval(clock);
  clock = null;
  held = null;
  keyboardPoint = null;
  bitmap?.close?.();
  bitmap = null;
  canvas.width = 1;
  canvas.height = 1;
  $("image-panel").hidden = true;
  stage.classList.remove("shielded");
  $("shield").hidden = true;
  $("metadata").replaceChildren();
  $("technical-data").replaceChildren();
  $("session-label").textContent = "";
}
function reset() {
  operation++;
  disposeImage();
  currentReport = null;
  $("file-card").hidden = true;
  $("empty").hidden = false;
  $("loading").hidden = true;
  $("result").hidden = true;
  $("file-input").value = "";
  $("file-name").textContent = "";
  $("file-size").textContent = "";
  $("checks").replaceChildren();
  $("issue-list").replaceChildren();
  setStatus("Current file cleared. Ready for another .GRD.");
  $("drop").focus();
}
function showFile(file) {
  $("file-card").hidden = false;
  $("file-name").textContent = file.name;
  $("file-size").textContent = bytesLabel(file.size);
}
function renderResult(report) {
  currentReport = report;
  $("download-plain").hidden = !(report.version >= 2 && report.viewable && report.regionVerified);
  $("plain-note").hidden = $("download-plain").hidden;
  $("download-proof").hidden = $("download-plain").hidden || !currentContainer?.manifest.visual || currentContainer.tiles.some(t=>t.sub);
  $("partial-visual-note").hidden = !currentContainer?.tiles.some(t=>t.sub);
  $("loading").hidden = true;
  $("result").hidden = false;
  $("empty").hidden = true;
  const genuine =
    report.genuine ||
    (report.viewable && report.regionVerified && report.trusted);
  const messages = {
    GENUINE: [
      "GENUINE",
      "FILE VERIFIED.",
      "Every section matched, the signature verified and the signer is pinned as trusted in this viewer.",
    ],
    TAMPERED: [
      "TAMPERED",
      "VERIFICATION FAILED.",
      "The image is withheld. One or more integrity or signer checks failed. Review the evidence below.",
    ],
    "NOT A GRD": [
      "NOT A GRD",
      "INVALID FILE.",
      "Choose a signed .GRD file. Renaming an ordinary image does not turn it into one.",
    ],
    UNSUPPORTED: [
      "UNSUPPORTED",
      "UNSUPPORTED.",
      "The browser, file version or image format is not supported. No genuine claim has been made.",
    ],
    "LIMIT EXCEEDED": [
      "LIMIT EXCEEDED",
      "FILE TOO LARGE.",
      "GRD1 allows 64 MiB, GRD2 32 MiB, and GRD3 256 MiB. The format-specific size limit was exceeded.",
    ],
    UNREADABLE: [
      "IMAGE UNREADABLE",
      "IMAGE UNREADABLE.",
      "The cryptographic checks passed, but the image header or decoder could not be safely read. It has not been displayed.",
    ],
    "CANNOT VERIFY": [
      "CANNOT VERIFY",
      "CHECK DID NOT FINISH.",
      "This viewer hit an internal limit or error before it could finish checking. This is not evidence of tampering. Try a current desktop browser or the Python checker (grd.py verify).",
    ],
  };
  messages["VERIFIED WITH REDACTIONS"] = [
    "VERIFIED WITH REDACTIONS",
    "RETAINED PIXELS VERIFIED.",
    report.subTile ? `${report.subTilesVisible} of ${report.subTilesTotal} cells at ${report.subTile}px match the trusted signer’s proof. Hidden cells are black. Redactor approval is not attested.` : `${report.tilesVisible} of ${report.tilesTotal} tiles match the trusted signer’s root. ${report.redactedTiles?.length} tiles were removed; their contents are not verified or shown. Redactor approval is not attested.`,
  ];
  messages.DEMO = [
    "DEMONSTRATION / NOT TRUSTED EVIDENCE",
    "REDACTION EXAMPLE.",
    `${report.subTilesVisible ?? report.tilesVisible} of ${report.subTilesTotal ?? report.tilesTotal} example regions retained. Test the mechanism, select tiles and export a copy. This self-signed demo does not establish a real signer’s identity.`,
  ];
  messages["UNVERIFIED: SELF-SIGNED"] = [
    "UNVERIFIED: SELF-SIGNED",
    "IDENTITY NOT VERIFIED.",
    `${report.subTilesVisible ?? report.tilesVisible} of ${report.subTilesTotal ?? report.tilesTotal} regions match this file’s signature. ${report.redactedTiles?.length || 0} tiles hidden. Anyone can edit an image and make a new self-signed file. Matching hashes only show consistency with this embedded key, not authenticity or identity.`,
  ];
  messages["UNTRUSTED SIGNER"] = [
    "UNTRUSTED SIGNER",
    "SIGNER NOT RECOGNISED.",
    "The tile proof matches this key, but its identity is not trusted by this viewer. Image withheld.",
  ];
  messages["REVOKED KEY"] = [
    "REVOKED KEY",
    "SIGNER REVOKED.",
    "This signing key is rejected by the bundled offline revocation policy. No before-revocation exception is made without validated timestamp evidence.",
  ];
  messages["FULLY REDACTED"] = [
    "FULLY REDACTED",
    "NO VISIBLE PIXELS.",
    "The signed root verifies, but all image tiles have been hidden. There is no retained visual content to call genuine.",
  ];
  const words = messages[report.verdict] ?? messages.TAMPERED;
  if (report.version >= 2 && report.genuine) {
    words[1] = "SIGNED TILE GRID VERIFIED.";
    words[2] =
      "Every tile matches the signed Merkle root and the signer is pinned as trusted. You can remove selected tiles while retaining proof for the rest.";
  }
  $("verdict-banner").className =
    "verdict-banner " +
    (report.personal
      ? "unverified"
      : report.demo
        ? "demo"
        : genuine
          ? "good"
          : report.verdict === "TAMPERED"
            ? "bad"
            : "neutral");
  $("verdict-kicker").textContent = words[0];
  $("verdict-title").textContent = words[1];
  $("verdict-description").textContent = words[2];
  const signerElem = $("verdict-signer");
  if (signerElem) {
    if (report.verdict === "GENUINE" || report.verdict === "VERIFIED WITH REDACTIONS") {
      const name = report.signerName || report.signer;
      const fp = report.fingerprint || report.keyId || "";
      if (name && fp) {
        signerElem.textContent = `Signed by ${name} and Fingerprint ${fp.slice(0, 16)}…`;
        signerElem.hidden = false;
      } else {
        signerElem.hidden = true;
      }
    } else if (report.verdict === "UNTRUSTED SIGNER") {
      const fp = report.fingerprint || report.keyId || "";
      signerElem.textContent = `${fp ? `Fingerprint ${fp}. ` : ""}Not in this viewer's trusted list. Compare this fingerprint with one the issuer gave you through a separate channel.`;
      signerElem.hidden = false;
    } else {
      signerElem.hidden = true;
    }
  }
  $("verdict-icon").textContent = genuine
    ? "✓"
    : report.verdict === "TAMPERED"
      ? "×"
      : "—";
  $("checks").replaceChildren();
  for (const item of report.checks) {
    const row = el(
      "div",
      undefined,
      "check-row " +
        (item.status === "pass"
          ? ""
          : item.status === "info"
            ? "informational"
            : "failed"),
    );
    row.append(
      el(
        "span",
        item.status === "pass" ? "✓" : item.status === "info" ? "i" : "×",
        "check-icon",
      ),
    );
    const copy = el("div");
    copy.append(el("strong", item.name), el("small", item.detail));
    row.append(
      copy,
      el(
        "span",
        item.status === "pass"
          ? "PASSED"
          : item.status === "info"
            ? report.personal
              ? "UNVERIFIED"
              : "DEMO ONLY"
            : "FAILED",
        "check-tag",
      ),
    );
    $("checks").append(row);
  }
  if (!report.checks.length) {
    const note = el(
      "p",
      "Verification stopped before the cryptographic checks.",
      "file-help",
    );
    $("checks").append(note);
  }
  $("issues").hidden = !report.problems.length;
  $("issue-list").replaceChildren(
    ...report.problems.map((text) => el("li", text)),
  );
  setStatus(words[0] + ". " + words[1]);
  $("verdict-title").focus({ preventScroll: true });
}
function pairs(target, rows) {
  target.replaceChildren();
  for (const [label, value] of rows) {
    if (value === undefined || value === null || value === "") continue;
    const row = el("div");
    row.append(
      el("dt", label),
      el("dd", typeof value === "object" ? JSON.stringify(value) : value),
    );
    target.append(row);
  }
}
function metadata(report) {
  const m = report.meta ?? {};
  pairs($("metadata"), [
    ["Asset ID", m.asset_id],
    ["Author · signed claim", m.author],
    ["Issued by · signed claim", m.issued_by],
    ["Public label · signed claim", m.original_filename],
    ["Dimensions", m.width + " × " + m.height + " px"],
    ["Time claimed by the signer", m.created_utc ?? m.created_melbourne],
    [report.demo ? "Demo signer" : "Signer", report.signer],
    [
      report.subTile ? "Retained cells" : "Retained tiles",
      report.version >= 2
        ? `${report.subTilesVisible ?? report.tilesVisible} / ${report.subTilesTotal ?? report.tilesTotal}`
        : undefined,
    ],
    ["Redacted tiles", report.redactedTiles?.length],
  ]);
  pairs($("technical-data"), [
    ["File SHA-256", report.fileHash],
    ["Signer key ID", report.keyId],
    ["Watermark ID · signed claim", m.watermark_id],
    ["Watermarks · signed claim", m.watermarks],
    ["Source · signed claim", m.source],
    [
      "Timestamp token",
      report.timestampPresent
        ? "Present · not validated by this viewer"
        : "Not present",
    ],
    ["Format", "GRD" + report.version],
    ["Signed Merkle root", report.root],
    [
      "Offline trust snapshot",
      report.revocation
        ? `${report.revocation.asOf} / version ${report.revocation.policyVersion}. Newer revocations may be unknown.`
        : undefined,
    ],
    ["Hidden rectangles · method is an unsigned claim", report.redactionMap],
    ["Viewer session", SESSION],
  ]);
  $("session-label").textContent = "SESSION / " + SESSION;
}
function shield(reason) {
  held = null;
  keyboardPoint = null;
  if (!bitmap) return;
  $("tile-overlay").hidden = true;
  stage.classList.add("shielded");
  $("shield").hidden = false;
  $("shield-reason").textContent = reason;
}
function setMode(localReveal) {
  reveal = localReveal;
  held = null;
  keyboardPoint = null;
  $("reveal-mode").setAttribute("aria-pressed", String(reveal));
  $("full-mode").setAttribute("aria-pressed", String(!reveal));
  $("reveal-hint").textContent = reveal
    ? "Hold a finger or pointer to reveal a spot. Keyboard: hold Space or Enter, move with arrow keys."
    : "Full view is visible with a session stamp. Choose Hold to reveal for a smaller viewing window.";
  queueDraw();
}
function showImage() {
  if (!bitmap) return;
  stage.classList.remove("shielded");
  $("shield").hidden = true;
  setMode(true);
  canvas.focus({ preventScroll: true });
  if (redactionEditing) {
    setMode(false);
    renderTileOverlay();
  }
  queueDraw();
}
function overlay(ctx, w, h) {
  const message =
    (currentReport?.demo
      ? "DEMO / NOT EVIDENCE · "
      : currentReport?.personal
        ? "UNVERIFIED: SELF-SIGNED · "
        : "GUARD · ") +
    SESSION +
    " · " +
    new Date().toISOString().slice(11, 19) +
    " UTC";
  ctx.save();
  ctx.globalAlpha = 0.35;
  ctx.font = `600 ${Math.max(12, Math.round(w / 44))}px Arial`;
  ctx.fillStyle = "#fff";
  ctx.strokeStyle = "#10271e";
  ctx.lineWidth = Math.max(1, w / 800);
  ctx.translate(w / 2, h / 2);
  ctx.rotate(-Math.PI / 8);
  const step = Math.max(80, h / 6),
    span = ctx.measureText(message).width + 90;
  for (let y = -h; y < h; y += step)
    for (let x = -w; x < w; x += span) {
      ctx.strokeText(message, x, y);
      ctx.fillText(message, x, y);
    }
  ctx.restore();
}
function draw() {
  drawQueued = false;
  if (!bitmap || stage.classList.contains("shielded") || document.hidden)
    return;
  const ctx = canvas.getContext("2d"),
    w = canvas.width,
    h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.save();
  if (reveal) {
    ctx.filter = `blur(${Math.max(8, Math.round(w / 45))}px)`;
    ctx.drawImage(bitmap, 0, 0, w, h);
    ctx.filter = "none";
    if (held) {
      const radius = Math.min(w, h) * 0.16;
      ctx.save();
      ctx.beginPath();
      ctx.arc(held.x, held.y, radius, 0, Math.PI * 2);
      ctx.clip();
      ctx.drawImage(bitmap, 0, 0, w, h);
      ctx.restore();
      ctx.beginPath();
      ctx.arc(held.x, held.y, radius, 0, Math.PI * 2);
      ctx.strokeStyle = "#f4f4dc";
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  } else ctx.drawImage(bitmap, 0, 0, w, h);
  overlay(ctx, w, h);
  if (currentReport?.redactionMap) {
    const m = currentReport.meta;
    for (const region of currentReport.redactionMap) {
      const x = (region.x * w) / m.width,
        y = (region.y * h) / m.height,
        rw = (region.width * w) / m.width,
        rh = (region.height * h) / m.height;
      ctx.strokeStyle = "#b7caff";
      ctx.lineWidth = 2;
      ctx.strokeRect(x + 1, y + 1, Math.max(0, rw - 2), Math.max(0, rh - 2));
      ctx.fillStyle = "#dbe5ff";
      ctx.font = `bold ${Math.max(7, Math.min(12, rw / 8))}px Arial`;
      ctx.fillText("REDACTED", x + 4, y + Math.min(rh - 3, 15));
    }
  }
  ctx.restore();
}
function queueDraw() {
  if (!drawQueued) {
    drawQueued = true;
    requestAnimationFrame(draw);
  }
}
function point(event) {
  const r = canvas.getBoundingClientRect();
  return {
    x: Math.max(
      0,
      Math.min(
        canvas.width,
        ((event.clientX - r.left) * canvas.width) / r.width,
      ),
    ),
    y: Math.max(
      0,
      Math.min(
        canvas.height,
        ((event.clientY - r.top) * canvas.height) / r.height,
      ),
    ),
  };
}

async function decode(report) {
  if (report.version === 3) {
    const blob = new Blob([containerImage(report.container)], {type:"image/png"});
    return await createImageBitmap(blob, {imageOrientation:"none"});
  }
  if (report.version >= 2) {
    const surface = document.createElement("canvas");
    surface.width = report.meta.width;
    surface.height = report.meta.height;
    surface
      .getContext("2d")
      .putImageData(
        new ImageData(
          new Uint8ClampedArray(report.imageRgba),
          surface.width,
          surface.height,
        ),
        0,
        0,
      );
    return typeof createImageBitmap === "function"
      ? await createImageBitmap(surface)
      : surface;
  }
  const m = report.meta,
    [width, height] = encodedDimensions(report.payload, m.mime);
  if (width !== m.width || height !== m.height)
    throw new Error(
      "Encoded image dimensions differ from the signed metadata.",
    );
  if (
    width * height > LIMITS.imagePixels ||
    Math.max(width, height) > LIMITS.dimension
  )
    throw new Error("Encoded image exceeds the safe viewing limits.");
  const blob = new Blob([report.payload], { type: m.mime });
  let image;
  if (typeof createImageBitmap === "function")
    image = await createImageBitmap(blob, { imageOrientation: "none" });
  else {
    const url = URL.createObjectURL(blob);
    try {
      image = new Image();
      image.src = url;
      await image.decode();
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  if (image.width !== width || image.height !== height) {
    image.close?.();
    throw new Error(
      "Decoded image dimensions differ from the signed metadata.",
    );
  }
  return image;
}
async function openFile(file) {
  const token = ++operation;
  disposeImage();
  currentReport = null;
  showFile(file);
  $("empty").hidden = true;
  $("result").hidden = true;
  $("loading").hidden = false;
  setStatus("Checking " + file.name + ".");
  let report;
  try {
    if (file.size > GRD3_LIMITS.bytes)
      report = {
        verdict: "LIMIT EXCEEDED",
        genuine: false,
        checks: [],
        problems: ["File exceeds the 256 MiB viewer limit."],
        failed: ["file size"],
        changed: ["file size"],
        byteLength: file.size,
      };
    else {
      const bytes = await file.arrayBuffer();
      report = await (isGRD2(bytes) ? verifyGRD2(bytes) : verifyGRD(bytes));
    }
    if (token !== operation) return;
    if (report.genuine || report.viewable) {
      try {
        const decoded = await decode(report);
        if (token !== operation) {
          decoded.close?.();
          return;
        }
        bitmap = decoded;
        report.checks.push({
          name:
            report.version >= 2 ? "Rendered tile grid" : "Image dimensions",
          status: "pass",
          detail:
            report.meta.width +
            " × " +
            report.meta.height +
            (report.version >= 2
              ? " · exact visible tiles; hidden tiles are placeholders"
              : " · encoded and decoded dimensions match"),
        });
      } catch (error) {
        report.genuine = false;
        report.viewable = false;
        report.verdict = "UNREADABLE";
        report.problems.push(error.message);
        report.checks.push({
          name: "Image decoding",
          status: "fail",
          detail: error.message,
        });
        delete report.payload;
      }
    }
    if (token !== operation) return;
    report.fileName = file.name;
    report.checkedAt = new Date().toISOString();
    report.viewerSession = SESSION;
    currentContainer = report.container ?? null;
    if (currentContainer) {
      const sealed = currentContainer.manifest.subTile || 64;
      for (const size of [8,16,32,64]) { $("grid-"+size).disabled = size < sealed; $("grid-"+size).checked = size === (sealed <= 16 ? 16 : sealed); }
    }
    delete report.container;
    delete report.imageRgba;
    renderResult(report);
    if ((report.genuine || report.viewable) && bitmap) {
      metadata(report);
      $("image-panel").hidden = false;
      const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      setMode(true);
      $("redaction-tools").hidden = !currentContainer;
      $("legacy-redaction-note").hidden = !!currentContainer;
      if (currentContainer) {
        $("redaction-status").textContent =
          `${report.tilesVisible} retained / ${report.tilesTotal} total. ${report.redactedTiles.length} already redacted. Choose Mark tiles to hide more.`;
        setMode(false);
      }
      queueDraw();
      clock = setInterval(queueDraw, 1000);
      if (document.hidden || !document.hasFocus())
        shield("The check finished while this window was away.");
    }
    // Release the raw image bytes once the display bitmap exists; reports never include pixels.
    delete report.payload;
  } catch (error) {
    if (token !== operation) return;
    renderResult({
      verdict: "UNSUPPORTED",
      genuine: false,
      checks: [],
      problems: ["The file could not be read: " + error.message],
      failed: [],
      changed: [],
      fileName: file.name,
      checkedAt: new Date().toISOString(),
      viewerSession: SESSION,
    });
  }
}
function download(contents, name, type) {
  const url = URL.createObjectURL(new Blob([contents], { type })),
    link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("drop").onclick = () => {
  $("file-input").click();
};
$("choose-another").onclick = () => $("file-input").click();
$("file-input").onchange = (event) => {
  const file = event.target.files[0];
  event.target.value = "";
  if (file) void openFile(file);
};
$("clear").onclick = reset;
$("cancel").onclick = reset;
$("drop").ondragover = (event) => {
  event.preventDefault();
  $("drop").classList.add("over");
};
$("drop").ondragleave = () => $("drop").classList.remove("over");
$("drop").ondrop = (event) => {
  event.preventDefault();
  $("drop").classList.remove("over");
  const files = event.dataTransfer.files;
  if (files.length) void openFile(files[0]);
};
window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => event.preventDefault());
$("download-report").onclick = () => {
  if (!currentReport) return;
  const report = {
    ...verificationReport(currentReport),
    scope:
      "Local GRD verification. GRD2 checks retained exact pixels against a signed root; redacted regions and redactor approval are not attested. Demo and self-signed files are not trusted evidence; anyone can edit and re-sign a replacement. Method labels are unsigned claims. Not proof of authorship, ownership, capture time or copy tracing.",
  };
  delete report.payload;
  download(
    JSON.stringify(report, null, 2),
    "guard-verification-" +
      (report.fileHash?.slice(0, 12) || "report") +
      ".json",
    "application/json",
  );
};
$("download-proof").onclick = async () => {
  if (!currentContainer) return;
  try { download(await exportProof(currentContainer), "image.grdp", "application/octet-stream"); setStatus("Visual proof downloaded. Keep it with copies you want to compare."); }
  catch (error) { setStatus("Visual proof export failed: " + error.message); }
};
$("download-plain").onclick = async () => {
  if (!currentContainer) return;
  try {
    const png = await exportPlainImage(currentContainer);
    download(png, "image.png", "image/png");
    setStatus("Plain image downloaded. This copy can no longer be verified as genuine.");
  } catch (error) { setStatus("Plain export failed: " + error.message); }
};
$("download-viewer").onclick = () =>
  download(ORIGINAL_HTML, "grd_viewer.html", "text/html");
$("reveal-mode").onclick = () => setMode(true);
$("full-mode").onclick = () => setMode(false);
$("hide-image").onclick = () => {
  shield(
    "You hid this image. Choose Show image again to return to hold-to-reveal mode.",
  );
  $("show-image").focus({ preventScroll: true });
};
$("show-image").onclick = showImage;
canvas.addEventListener("pointerdown", (event) => {
  if (!bitmap || stage.classList.contains("shielded")) return;
  held = point(event);
  canvas.setPointerCapture(event.pointerId);
  queueDraw();
});
canvas.addEventListener("pointermove", (event) => {
  if (held && canvas.hasPointerCapture(event.pointerId)) {
    held = point(event);
    queueDraw();
  }
});
for (const name of ["pointerup", "pointercancel", "lostpointercapture"])
  canvas.addEventListener(name, () => {
    held = null;
    queueDraw();
  });
canvas.addEventListener("keydown", (event) => {
  if (!bitmap || !reveal || stage.classList.contains("shielded")) return;
  if (
    [
      " ",
      "Enter",
      "ArrowLeft",
      "ArrowRight",
      "ArrowUp",
      "ArrowDown",
      "Escape",
    ].includes(event.key)
  )
    event.preventDefault();
  if (event.key === "Escape") {
    held = null;
    queueDraw();
    return;
  }
  if (event.key === " " || event.key === "Enter") {
    keyboardPoint ??= { x: canvas.width / 2, y: canvas.height / 2 };
    held = keyboardPoint;
    queueDraw();
  }
  if (event.key.startsWith("Arrow")) {
    keyboardPoint ??= { x: canvas.width / 2, y: canvas.height / 2 };
    const step = Math.max(10, Math.min(canvas.width, canvas.height) / 12);
    if (event.key === "ArrowLeft")
      keyboardPoint.x = Math.max(0, keyboardPoint.x - step);
    if (event.key === "ArrowRight")
      keyboardPoint.x = Math.min(canvas.width, keyboardPoint.x + step);
    if (event.key === "ArrowUp")
      keyboardPoint.y = Math.max(0, keyboardPoint.y - step);
    if (event.key === "ArrowDown")
      keyboardPoint.y = Math.min(canvas.height, keyboardPoint.y + step);
    if (held) held = keyboardPoint;
    queueDraw();
  }
});
canvas.addEventListener("keyup", (event) => {
  if (event.key === " " || event.key === "Enter") {
    held = null;
    queueDraw();
  }
});
canvas.addEventListener("blur", () => {
  held = null;
  queueDraw();
});
canvas.addEventListener("contextmenu", (event) => event.preventDefault());
document.addEventListener("visibilitychange", () => {
  if (document.hidden)
    shield("The image was hidden because you switched tabs or apps.");
});
window.addEventListener("blur", () =>
  shield("The image was hidden because this window lost focus."),
);
window.addEventListener("beforeprint", () =>
  shield("Protected image content is not included in printouts."),
);
window.addEventListener("keydown", (event) => {
  if (event.key === "PrintScreen")
    shield(
      "The screenshot key was detected. Browsers cannot reliably block screenshots.",
    );
});
window.addEventListener("pagehide", () => {
  operation++;
  disposeImage();
});
// Compatibility entry point; trust anchors are closed over and cannot be changed through this API.
window.verifyGRD = (input) =>
  isGRD2(input) ? verifyGRD2(input) : verifyGRD(input);

function redactionGrid() {
  if (!currentContainer?.manifest.subTile) return 64;
  return [8,16,32,64].find(size => $("grid-"+size).checked) || 16;
}
function gridBounds(index) {
  const m=currentContainer.manifest,g=redactionGrid(),cols=Math.ceil(m.width/g),x=(index%cols)*g,y=Math.floor(index/cols)*g;
  return {x,y,width:Math.min(g,m.width-x),height:Math.min(g,m.height-y)};
}
function gridHidden(index) {
  const b=gridBounds(index);
  return (currentReport?.redactionMap || []).some(r=>r.x<=b.x&&r.y<=b.y&&r.x+r.width>=b.x+b.width&&r.y+r.height>=b.y+b.height);
}
function gridForRect(m,rect) {
  const g=redactionGrid(),cols=Math.ceil(m.width/g),rows=Math.ceil(m.height/g),out=[];
  if (![rect.x,rect.y,rect.width,rect.height].every(Number.isFinite)||rect.width<=0||rect.height<=0) throw new Error("Enter a rectangle with positive width and height.");
  for(let row=Math.max(0,Math.floor(rect.y/g));row<Math.min(rows,Math.ceil((rect.y+rect.height)/g));row++)
    for(let col=Math.max(0,Math.floor(rect.x/g));col<Math.min(cols,Math.ceil((rect.x+rect.width)/g));col++)out.push(row*cols+col);
  return out;
}
function positionTileOverlay() {
  if (!currentContainer || !redactionEditing) return;
  const overlay=$("tile-overlay"),m=currentContainer.manifest,g=redactionGrid(),box=canvas.getBoundingClientRect();
  overlay.style.width=box.width+"px";overlay.style.height=box.height+"px";
  overlay.style.gridTemplateColumns=Array.from({length:Math.ceil(m.width/g)},(_,i)=>Math.min(g,m.width-i*g)+"fr").join(" ");
  overlay.style.gridTemplateRows=Array.from({length:Math.ceil(m.height/g)},(_,i)=>Math.min(g,m.height-i*g)+"fr").join(" ");
}
function renderTileOverlay() {
  const overlay=$("tile-overlay"),active=overlay.contains(document.activeElement)?document.activeElement.dataset.tileIndex:null;
  overlay.hidden=!redactionEditing||!currentContainer||stage.classList.contains("shielded");overlay.replaceChildren();if(overlay.hidden)return;
  const m=currentContainer.manifest,g=redactionGrid(),cols=Math.ceil(m.width/g),count=cols*Math.ceil(m.height/g);
  if(count>4096){
    // Dense grids stay bounded in the DOM. Keyboard users select through the rectangle fields.
    const mask=el("canvas");mask.width=canvas.width;mask.height=canvas.height;mask.setAttribute("aria-hidden","true");
    mask.style.cssText="position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
    const ctx=mask.getContext("2d");ctx.fillStyle="rgba(55,80,220,.45)";
    for(const index of selectedTiles){const b=gridBounds(index);ctx.fillRect(b.x/m.width*mask.width,b.y/m.height*mask.height,b.width/m.width*mask.width,b.height/m.height*mask.height);}
    overlay.append(mask);
    $("redaction-status").textContent=`${selectedTiles.size} cells selected at ${g}px. This dense grid uses the rectangle fields or drag selection instead of individual buttons.`;
  } else {
    let first=true;
    for(let index=0;index<count;index++){
      const hidden=gridHidden(index),chosen=selectedTiles.has(index),button=el("button",hidden?"HIDDEN":chosen?"HIDE":"+",hidden?"tile-hidden":chosen?"tile-selected":"tile-visible");
      button.type="button";button.dataset.tileIndex=String(index);button.disabled=hidden;button.tabIndex=!hidden&&(active!==null?String(index)===active:first)?0:-1;if(!hidden)first=false;
      button.setAttribute("aria-label",`Cell ${index+1}, row ${Math.floor(index/cols)+1}, column ${index%cols+1}, ${g}px${hidden?", already hidden":""}`);button.setAttribute("aria-pressed",String(chosen));
      button.onclick=()=>{if(selectedTiles.has(index))selectedTiles.delete(index);else selectedTiles.add(index);renderTileOverlay();$("export-redacted").disabled=!selectedTiles.size;$("redaction-status").textContent=`${selectedTiles.size} cells selected at ${g}px. Apply them by exporting a redacted copy.`;};overlay.append(button);
    }
  }
  positionTileOverlay();if(active!==null)overlay.querySelector(`[data-tile-index="${active}"]`)?.focus({preventScroll:true});
}
for(const size of [8,16,32,64])$("grid-"+size).onchange=()=>{selectedTiles.clear();$("export-redacted").disabled=true;renderTileOverlay();};
$("redact-mode").onclick = () => {
  redactionEditing = !redactionEditing;
  $("redact-mode").setAttribute("aria-pressed", String(redactionEditing));
  $("redact-mode").textContent = redactionEditing
    ? "Finish marking"
    : "Mark tiles";
  if (redactionEditing) setMode(false);
  renderTileOverlay();
};
new ResizeObserver(positionTileOverlay).observe(canvas);
$("export-redacted").onclick = async () => {
  if (!currentContainer || !selectedTiles.size) return;
  const source = currentContainer,
    selection = [...selectedTiles],
    token = operation;
  $("export-redacted").disabled = true;
  try {
    const bytes = source.manifest.subTile ? await redactRects(source,selection.map(gridBounds),{granularity:redactionGrid()}) : await redactGRD2(source, selection, "black");
    if (operation !== token || currentContainer !== source) return;
    const name =
      (currentReport.fileName ?? "image.GRD").replace(
        /(?:\.redacted)?\.grd$/i,
        "",
      ) + ".redacted.GRD";
    download(bytes, name, "application/octet-stream");
    await openFile(new File([bytes], name));
    setStatus(
      "Redacted copy exported. The selected tiles were replaced and their original salts were removed.",
    );
  } catch (error) {
    if (operation === token) {
      $("redaction-status").textContent = "Export failed: " + error.message;
      $("export-redacted").disabled = false;
    }
  }
};
$("try-redaction").onclick = async () => {
  const token = operation;
  $("try-redaction").disabled = true;
  try {
    const sample = document.createElement("canvas");
    sample.width = 384;
    sample.height = 256;
    const ctx = sample.getContext("2d");
    ctx.fillStyle = "#eef0f5";
    ctx.fillRect(0, 0, 384, 256);
    ctx.fillStyle = "#17213b";
    ctx.fillRect(0, 0, 384, 48);
    ctx.fillStyle = "#fff";
    ctx.font = "bold 19px Arial";
    ctx.fillText("DEMONSTRATION IMAGE", 16, 31);
    ctx.fillStyle = "#9aaee3";
    ctx.beginPath();
    ctx.arc(90, 112, 33, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#35456d";
    ctx.fillRect(47, 146, 86, 59);
    ctx.fillStyle = "#17213b";
    ctx.font = "bold 13px Arial";
    ctx.fillText("FICTIONAL PERSON", 174, 94);
    ctx.font = "12px Arial";
    ctx.fillText("EXAMPLE ADDRESS", 174, 128);
    ctx.fillText("123 SAMPLE STREET", 174, 149);
    ctx.fillText("ID: 000-123", 174, 184);
    ctx.fillStyle = "#214eef";
    ctx.fillRect(16, 224, 352, 2);
    ctx.font = "10px Arial";
    ctx.fillText("EXAMPLE ONLY / SELECT TILES TO REDACT", 16, 242);
    const key = await crypto.subtle.generateKey({ name: "Ed25519" }, false, [
        "sign",
        "verify",
      ]),
      publicKey = new Uint8Array(
        await crypto.subtle.exportKey("raw", key.publicKey),
      );
    const doc = await sealRgba({
      rgba: new Uint8Array(ctx.getImageData(0, 0, 384, 256).data),
      width: 384,
      height: 256,
      tileSize: 64,
      publicKey,
      purpose: "demo",
      subTile: 16,
      label: "Demonstration only",
      sign: (bytes) =>
        crypto.subtle.sign({ name: "Ed25519" }, key.privateKey, bytes),
    });
    if (operation !== token) return;
    await openFile(new File([encodeGRD2(doc)], "redaction-example.GRD"));
    $("image-panel").scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
      block: "start",
    });
  } catch (error) {
    setStatus("The demo could not start: " + error.message);
    $("file-help").textContent =
      "The demo needs browser Ed25519 support: " + error.message;
  } finally {
    $("try-redaction").disabled = false;
  }
};

function setTileSelection(indices) {
  for (const index of indices) if (!gridHidden(index)) selectedTiles.add(index);
  renderTileOverlay();$("export-redacted").disabled=!selectedTiles.size;
  $("redaction-status").textContent=`${selectedTiles.size} cells selected. Export rounds to ${redactionGrid()}px boundaries.`;
}
$("select-rectangle").onclick = () => {
  if (!currentContainer) return;
  try {
    redactionEditing = true;
    $("redact-mode").setAttribute("aria-pressed", "true");
    $("redact-mode").textContent = "Finish marking";
    setMode(false);
    setTileSelection(
      gridForRect(currentContainer.manifest, {
        x: Number($("rect-x").value),
        y: Number($("rect-y").value),
        width: Number($("rect-width").value),
        height: Number($("rect-height").value),
      }),
    );
  } catch (error) {
    $("redaction-status").textContent = error.message;
  }
};
let rectangleStart = null,
  rectangleMoved = false,
  skipTileClick = false;
const overlayElement = $("tile-overlay");
function imagePoint(event) {
  const box = canvas.getBoundingClientRect(),
    m = currentContainer.manifest;
  return {
    x: Math.max(
      0,
      Math.min(m.width, ((event.clientX - box.left) * m.width) / box.width),
    ),
    y: Math.max(
      0,
      Math.min(m.height, ((event.clientY - box.top) * m.height) / box.height),
    ),
  };
}
overlayElement.addEventListener("pointerdown", (event) => {
  if (!currentContainer || !redactionEditing) return;
  rectangleStart = imagePoint(event);
  rectangleMoved = false;
});
overlayElement.addEventListener("pointermove", (event) => {
  if (!rectangleStart || !currentContainer) return;
  const p = imagePoint(event);
  if (Math.abs(p.x - rectangleStart.x) + Math.abs(p.y - rectangleStart.y) > 8) {
    rectangleMoved = true;
    overlayElement.setPointerCapture(event.pointerId);
  }
});
overlayElement.addEventListener("pointerup", (event) => {
  if (!rectangleStart || !currentContainer) return;
  const start = rectangleStart;
  rectangleStart = null;
  if (!rectangleMoved) return;
  const p = imagePoint(event);
  skipTileClick = true;
  event.preventDefault();
  setTileSelection(
    gridForRect(currentContainer.manifest, {
      x: Math.min(start.x, p.x),
      y: Math.min(start.y, p.y),
      width: Math.max(1, Math.abs(start.x - p.x)),
      height: Math.max(1, Math.abs(start.y - p.y)),
    }),
  );
  setTimeout(() => (skipTileClick = false), 0);
});
overlayElement.addEventListener("pointercancel", () => {
  rectangleStart = null;
  rectangleMoved = false;
});
overlayElement.addEventListener(
  "click",
  (event) => {
    if (skipTileClick) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  },
  true,
);
overlayElement.addEventListener("keydown", (event) => {
  if (!currentContainer || !event.key.startsWith("Arrow")) return;
  const i = Number(event.target.dataset.tileIndex),
    cols = Math.ceil(currentContainer.manifest.width / redactionGrid());
  if (!Number.isInteger(i)) return;
  const step =
    event.key === "ArrowLeft"
      ? -1
      : event.key === "ArrowRight"
        ? 1
        : event.key === "ArrowUp"
          ? -cols
          : cols;
  let next = i + step;
  while (next >= 0 && next < currentContainer.tiles.length) {
    const button = overlayElement.querySelector(`[data-tile-index="${next}"]`);
    if (button && !button.disabled) {
      event.target.tabIndex = -1;
      button.tabIndex = 0;
      button.focus();
      break;
    }
    next += step;
  }
  event.preventDefault();
});

let conversionImage = null,
  conversionVersion = 0,
  conversionPreviewUrl = null;
function conversionStatus(message, error = false) {
  $("convert-status").textContent = message;
  $("convert-status").classList.toggle("error", error);
  $("convert-input").setAttribute("aria-invalid", String(error));
}
$("convert-input").onchange = async () => {
  const token = ++conversionVersion,
    file = $("convert-input").files[0];
  conversionImage = null;
  $("convert-preview").hidden = true;
  $("convert-image").removeAttribute("src");
  if (conversionPreviewUrl) URL.revokeObjectURL(conversionPreviewUrl);
  conversionPreviewUrl = null;
  if (!file) {
    conversionStatus("Choose an image to begin.");
    return;
  }
  conversionStatus("Reading image locally…");
  let decoded;
  try {
    if (file.size > GRD3_LIMITS.bytes)
      throw new Error("Choose an image up to 256 MiB.");
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (token !== conversionVersion) return;
    const allowResize = $("convert-resize").checked;
    const info = inspectConversionImage(bytes, { allowResize, large: true });
    decoded = await createImageBitmap(new Blob([bytes], { type: info.mime }));
    if (token !== conversionVersion) return;
    if (
      !decoded.width ||
      !decoded.height ||
      decoded.width > 16384 ||
      decoded.height > 16384 ||
      decoded.width * decoded.height > 50_000_000 ||
      decoded.width * decoded.height !== info.width * info.height
    )
      throw new Error(
        "Decoded image dimensions are unsupported. Export it to PNG and try again.",
      );
    const originalWidth = decoded.width,
      originalHeight = decoded.height;
    const fitted = fitConversionDimensions(originalWidth, originalHeight, { large: true });
    const resized =
      fitted.width !== originalWidth || fitted.height !== originalHeight;
    if (resized && !allowResize)
      throw new Error("Enable “Fit large photos” to convert this image here.");
    const surface = document.createElement("canvas");
    surface.width = fitted.width;
    surface.height = fitted.height;
    const context = surface.getContext("2d", { willReadFrequently: true });
    context.fillStyle = "#fff";
    context.fillRect(0, 0, surface.width, surface.height);
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    context.drawImage(decoded, 0, 0, surface.width, surface.height);
    decoded.close();
    const rgba = new Uint8Array(
      context.getImageData(0, 0, surface.width, surface.height).data,
    );
    const preview = await new Promise((resolve) =>
      surface.toBlob(resolve, "image/png"),
    );
    if (token !== conversionVersion) return;
    if (!preview)
      throw new Error("Could not prepare this image. Try a PNG or JPG export.");
    conversionImage = {
      rgba,
      width: surface.width,
      height: surface.height,
      name: file.name,
      sourceBytes: file.size,
    };
    conversionPreviewUrl = URL.createObjectURL(preview);
    $("convert-image").src = conversionPreviewUrl;
    $("convert-details").textContent =
      `${file.name} · ${resized ? `Original ${originalWidth} × ${originalHeight} → GRD ${surface.width} × ${surface.height} · output limit 36 MP / 9,000 tiles` : `${surface.width} × ${surface.height} · original size`} · ${bytesLabel(file.size)}`;
    $("convert-preview").hidden = false;
    conversionStatus(
      (resized
        ? "Ready. The GRD will use the resized preview above. Your original stays unchanged. "
        : "Ready at original size. ") +
        "Self-signed; transparency becomes white and animation uses the first frame. Source metadata is not copied.",
    );
  } catch (error) {
    if (token === conversionVersion)
      conversionStatus(
        error.message ||
          "This browser cannot decode that image. Try PNG or JPG.",
        true,
      );
  } finally {
    decoded?.close?.();
  }
};
$("convert-resize").onchange = () => $("convert-input").onchange();
$("convert-form").onsubmit = async (event) => {
  event.preventDefault();
  if ($("convert-submit").disabled) return;
  if (!conversionImage) {
    conversionStatus(
      "Choose a supported image and wait for its preview before converting.",
      true,
    );
    $("convert-input").focus();
    return;
  }
  const source = conversionImage,
    token = conversionVersion,
    viewerToken = operation;
  $("convert-submit").disabled = true;
  $("convert-input").disabled = true;
  $("convert-resize").disabled = true;
  $("convert-form").setAttribute("aria-busy", "true");
  conversionStatus("Converting and signing on your device…");
  try {
    const key = await crypto.subtle.generateKey({ name: "Ed25519" }, false, [
      "sign",
      "verify",
    ]);
    const publicKey = new Uint8Array(
      await crypto.subtle.exportKey("raw", key.publicKey),
    );
    const doc = await sealRgba({
      rgba: source.rgba,
      width: source.width,
      height: source.height,
      publicKey,
      purpose: "personal",
      subTile: 16,
      label: "",
      sign: (b) => crypto.subtle.sign("Ed25519", key.privateKey, b),
    });
    const bytes = encodeGRD2(doc),
      result = await verifyGRD2(bytes);
    if (result.verdict !== "UNVERIFIED: SELF-SIGNED" || !result.viewable)
      throw new Error(
        "The generated file did not pass its integrity check. No download was created.",
      );
    if (token !== conversionVersion || viewerToken !== operation)
      throw new Error(
        "Another file was opened. Convert again when you are ready.",
      );
    const name = "image.GRD";
    const W = source.width,
      H = source.height,
      ratio = (bytes.length / source.sourceBytes).toFixed(1);
    let statusMsg = `Downloaded image.GRD · ${W} × ${H} · ${bytesLabel(bytes.length)} (${ratio}× the original file). Guard stores exact lossless pixels so every tile can be checked. Unverified: self-signed.`;
    if (bytes.length > 20 * 1024 * 1024)
      statusMsg += " Large file: some phones may be slow to open it.";
    conversionStatus(statusMsg);
    download(bytes, name, "application/octet-stream");
    await openFile(new File([bytes], name));
    $("convert-status").tabIndex = -1;
    $("convert-status").focus();
  } catch (error) {
    conversionStatus("Conversion failed: " + error.message, true);
  } finally {
    $("convert-submit").disabled = false;
    $("convert-input").disabled = false;
    $("convert-resize").disabled = false;
    $("convert-form").removeAttribute("aria-busy");
  }
};

$("copy-form").onsubmit = async event => {
  event.preventDefault();
  if ($("copy-submit").disabled) return;
  const proofFile = $("copy-proof").files[0], imageFile = $("copy-image").files[0];
  if (!proofFile || !imageFile) { $("copy-status").textContent = "Choose both the visual proof and image copy."; return; }
  $("copy-submit").disabled = true; $("copy-proof").disabled = true; $("copy-image").disabled = true; $("copy-form").setAttribute("aria-busy", "true");
  $("copy-status").classList.remove("borderline");
  $("copy-status").textContent = "Checking signature, disclosures and visual block averages locally…";
  try {
    if (proofFile.size > 16*1024*1024 || imageFile.size > GRD3_LIMITS.bytes) throw new Error("Proof must be at most 16 MiB and the image at most 256 MiB.");
    const r = await verifyVisual(new Uint8Array(await proofFile.arrayBuffer()), new Uint8Array(await imageFile.arrayBuffer()));
    const label = r.visualVerdict ?? r.verdict;
    $("copy-status").classList.toggle("borderline", label === "BORDERLINE (decoder-dependent)");
    $("copy-status").textContent = label + ". " + (r.trustVerdict && !r.trusted ? r.trustVerdict + ": signer identity is not verified. " : "") +
      (r.worstError !== undefined ? "Largest block difference: " + r.worstError + " / 255. " : "") + r.guarantee +
      (r.problems.length ? " " + r.problems.join(" ") : "");
  } catch (error) { $("copy-status").textContent = "Copy check could not finish: " + error.message; }
  finally { $("copy-submit").disabled = false; $("copy-proof").disabled = false; $("copy-image").disabled = false; $("copy-form").removeAttribute("aria-busy"); $("copy-status").focus(); }
};
