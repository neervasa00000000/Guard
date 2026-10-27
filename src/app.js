const $ = (id) => document.getElementById(id);
const ORIGINAL_HTML = "<!doctype html>\n" + document.documentElement.outerHTML;
const SESSION = hex(crypto.getRandomValues(new Uint8Array(8))).toUpperCase();
let operation = 0,
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
  $("loading").hidden = true;
  $("result").hidden = false;
  $("empty").hidden = true;
  const genuine = report.genuine;
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
      "Choose a .GRD up to 64 MiB. The file was not read into memory.",
    ],
    UNREADABLE: [
      "IMAGE UNREADABLE",
      "IMAGE UNREADABLE.",
      "The cryptographic checks passed, but the image header or decoder could not be safely read. It has not been displayed.",
    ],
  };
  const words = messages[report.verdict] ?? messages.TAMPERED;
  $("verdict-banner").className =
    "verdict-banner " +
    (genuine ? "good" : report.verdict === "TAMPERED" ? "bad" : "neutral");
  $("verdict-kicker").textContent = words[0];
  $("verdict-title").textContent = words[1];
  $("verdict-description").textContent = words[2];
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
      "check-row " + (item.status === "pass" ? "" : "failed"),
    );
    row.append(el("span", item.status === "pass" ? "✓" : "×", "check-icon"));
    const copy = el("div");
    copy.append(el("strong", item.name), el("small", item.detail));
    row.append(
      copy,
      el("span", item.status === "pass" ? "PASSED" : "FAILED", "check-tag"),
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
    ["Original file", m.original_filename],
    ["Dimensions", m.width + " × " + m.height + " px"],
    ["Created · signed claim", m.created_utc ?? m.created_melbourne],
    ["Trusted signer", report.signer],
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
    ["Format", "GRD1 / version " + report.version],
    ["Viewer session", SESSION],
  ]);
  $("session-label").textContent = "SESSION / " + SESSION;
}
function shield(reason) {
  held = null;
  keyboardPoint = null;
  if (!bitmap) return;
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
  queueDraw();
}
function overlay(ctx, w, h) {
  const message =
    "GUARD · " +
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
    if (file.size > LIMITS.fileBytes)
      report = {
        verdict: "LIMIT EXCEEDED",
        genuine: false,
        checks: [],
        problems: ["File exceeds the 64 MiB viewer limit."],
        failed: ["file size"],
        changed: ["file size"],
        byteLength: file.size,
      };
    else report = await verifyGRD(await file.arrayBuffer());
    if (token !== operation) return;
    if (report.genuine) {
      try {
        const decoded = await decode(report);
        if (token !== operation) {
          decoded.close?.();
          return;
        }
        bitmap = decoded;
        report.checks.push({
          name: "Image dimensions",
          status: "pass",
          detail:
            report.meta.width +
            " × " +
            report.meta.height +
            " · encoded and decoded dimensions match",
        });
      } catch (error) {
        report.genuine = false;
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
    renderResult(report);
    if (report.genuine && bitmap) {
      metadata(report);
      $("image-panel").hidden = false;
      const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      setMode(true);
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
    ...currentReport,
    scope:
      "Local GRD1 verification using pinned viewer keys. Not proof of authorship, ownership, timestamp authority validation or copy tracing.",
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
window.verifyGRD = verifyGRD;
