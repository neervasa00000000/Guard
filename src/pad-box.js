// SPDX-License-Identifier: MIT
function snapAxis(start, size, limit, grid) {
  if (!Number.isFinite(start) || !Number.isFinite(size) || start < 0 || start >= limit || size <= 0)
    throw new RangeError("Enter an area inside the picture with a positive width and height.");
  const left = Math.floor(start / grid) * grid;
  const right = Math.ceil(Math.min(limit, start + size) / grid) * grid;
  return [left, Math.min(limit, Math.max(left + grid, right))];
}

// Choose the closest centred, grid-aligned start that still covers both ends.
// A partial edge tile can make an edge-clamped box slightly wider than its class.
function growAxis([start, end], target, limit, grid) {
  if (target >= limit) return [0, limit];
  const low = Math.ceil(Math.max(0, end - target) / grid) * grid;
  const high = Math.floor(Math.min(start, limit - target) / grid) * grid;
  if (low > high) return [high, limit];
  const centre = Math.floor((start + end - target) / (2 * grid) + 0.5) * grid;
  const left = Math.max(low, Math.min(high, centre));
  return [left, left + target];
}

export function padBox({ x, y, w, h }, { grid, widthClass = 128, lineHeight = 32, imgW, imgH }) {
  if (![grid, imgW, imgH].every(n => Number.isSafeInteger(n) && n > 0) ||
      ![widthClass, lineHeight].every(n => Number.isSafeInteger(n) && n >= 0) ||
      widthClass % grid !== 0)
    throw new RangeError("Invalid grid, padding or image size.");
  let horizontal = snapAxis(x, w, imgW, grid);
  let vertical = snapAxis(y, h, imgH, grid);
  if (widthClass) {
    const width = Math.ceil((horizontal[1] - horizontal[0]) / widthClass) * widthClass;
    horizontal = growAxis(horizontal, width, imgW, grid);
  }
  if (lineHeight > vertical[1] - vertical[0]) {
    vertical = growAxis(vertical, Math.ceil(lineHeight / grid) * grid, imgH, grid);
  }
  return { x: horizontal[0], y: vertical[0], w: horizontal[1] - horizontal[0], h: vertical[1] - vertical[0] };
}

// Measure the union so overlapping selections are counted once.
export function boxUnionArea(boxes) {
  const edges = [...new Set(boxes.flatMap(({ x, w }) => [x, x + w]))].sort((a, b) => a - b);
  let area = 0;
  for (let i = 1; i < edges.length; i++) {
    const left = edges[i - 1], right = edges[i];
    const rows = boxes.filter(b => b.x < right && b.x + b.w > left).sort((a, b) => a.y - b.y);
    let covered = 0, bottom = 0;
    for (const { y, h } of rows) {
      covered += Math.max(0, y + h - Math.max(bottom, y));
      bottom = Math.max(bottom, y + h);
    }
    area += (right - left) * covered;
  }
  return area;
}
