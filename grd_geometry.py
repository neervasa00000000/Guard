"""TileSeal blackout geometry. This module does not read or modify proofs."""
import math


def _snap_axis(start, size, limit, grid):
    if not (math.isfinite(start) and math.isfinite(size) and 0 <= start < limit and size > 0):
        raise ValueError("Enter an area inside the picture with a positive width and height.")
    left = math.floor(start / grid) * grid
    right = math.ceil(min(limit, start + size) / grid) * grid
    return left, min(limit, max(left + grid, right))


def _grow_axis(bounds, target, limit, grid):
    start, end = bounds
    if target >= limit:
        return 0, limit
    low = math.ceil(max(0, end - target) / grid) * grid
    high = math.floor(min(start, limit - target) / grid) * grid
    if low > high:
        return high, limit
    centre = math.floor((start + end - target) / (2 * grid) + 0.5) * grid
    left = max(low, min(high, centre))
    return left, left + target


def pad_box(rect, *, grid, img_w, img_h, width_class=128, line_height=32):
    """Round outward, then grow to a width class and minimum line height."""
    if (any(type(n) is not int or n <= 0 for n in (grid, img_w, img_h))
            or any(type(n) is not int or n < 0 for n in (width_class, line_height))
            or width_class % grid):
        raise ValueError("Invalid grid, padding or image size.")
    x, y, width, height = rect
    horizontal = _snap_axis(x, width, img_w, grid)
    vertical = _snap_axis(y, height, img_h, grid)
    if width_class:
        width = math.ceil((horizontal[1] - horizontal[0]) / width_class) * width_class
        horizontal = _grow_axis(horizontal, width, img_w, grid)
    if line_height > vertical[1] - vertical[0]:
        target = math.ceil(line_height / grid) * grid
        vertical = _grow_axis(vertical, target, img_h, grid)
    left, right = horizontal
    top, bottom = vertical
    return left, top, right - left, bottom - top
