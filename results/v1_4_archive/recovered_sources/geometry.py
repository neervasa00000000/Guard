"""Relative text bounds, redaction policies, and exact horizontal likelihoods."""

from dataclasses import dataclass

import numpy as np


PADDING_WIDTHS = (32, 64, 96, 128, 192, 256)


@dataclass(frozen=True)
class Policy:
    kind: str
    width: int = 1

    @property
    def label(self):
        return self.kind if self.kind == "exact" else f"{self.kind}-{self.width}"


POLICIES = (
    Policy("exact"),
    *(Policy("square", width) for width in (8, 16, 32, 64, 128)),
    *(Policy("width-grid", width) for width in (16, 64, 128)),
    *(Policy(kind, width) for kind in ("ink-anchored", "pen-anchored")
      for width in PADDING_WIDTHS),
)


def text_bounds(font, text, model):
    """Return an unpadded, half-open box in pen and baseline coordinates."""
    if model == "LAYOUT-BOX":
        return font.getbbox(text, anchor="ls")
    if model == "PIXEL-INK":
        mask, (mask_left, mask_top) = font.getmask2(text, mode="L", anchor="ls")
        ink = mask.getbbox()
        if ink is None:
            raise ValueError(f"Text has no ink: {text!r}")
        left, top, right, bottom = ink
        return left + mask_left, top + mask_top, right + mask_left, bottom + mask_top
    raise ValueError(f"Unknown observation model: {model}")


def ceil_multiple(value, width):
    return -(-value // width) * width


class Geometry:
    """Vectorized candidate boxes for one dictionary, font, and size."""

    def __init__(self, bounds, line_top, line_bottom):
        self.left, self.top, self.right, self.bottom = np.asarray(bounds, dtype=np.int64).T
        self.line_top = min(line_top, int(self.top.min())) - 1
        self.line_bottom = max(line_bottom, int(self.bottom.max())) + 1
        self.fixed_left = int(self.left.min()) - 1
        self.left = self.left - 1
        self.top = self.top - 1
        self.right = self.right + 1
        self.bottom = self.bottom + 1

    def horizontal(self, policy):
        if policy.kind == "pen-anchored":
            # Bucket the entire span from the fixed anchor to the padded right
            # edge, so the selected box covers every target assigned to it.
            left = np.full_like(self.left, self.fixed_left)
            return left, left + ceil_multiple(self.right - left, policy.width)
        if policy.kind == "ink-anchored":
            return self.left, self.left + ceil_multiple(self.right - self.left, policy.width)
        return self.left, self.right

    def vertical(self, policy, baseline):
        if policy.kind in {"ink-anchored", "pen-anchored", "width-grid"}:
            return self.line_top + baseline, self.line_bottom + baseline
        if policy.kind == "square":
            top = (self.top + baseline) // policy.width * policy.width
            return top, ceil_multiple(self.bottom + baseline, policy.width)
        return self.top + baseline, self.bottom + baseline

    def observe(self, policy, target, pen, baseline):
        left, right = self.horizontal(policy)
        left, right = left[target] + pen, right[target] + pen
        if policy.kind in {"square", "width-grid"}:
            left = left // policy.width * policy.width
            right = ceil_multiple(right, policy.width)
        top, bottom = self.vertical(policy, baseline)
        if np.ndim(top):
            top, bottom = top[target], bottom[target]
        return int(left), int(top), int(right), int(bottom)

    def counts(self, policy, observed, baseline, pen_min, pen_max):
        """Count integer pen positions in the inclusive support for each candidate."""
        x0, y0, x1, y1 = observed
        left, right = self.horizontal(policy)
        top, bottom = self.vertical(policy, baseline)
        width = policy.width if policy.kind in {"square", "width-grid"} else 1
        # floor((pen + left) / width) * width == x0
        # ceil((pen + right) / width) * width == x1
        lower = np.maximum(np.maximum(x0 - left, x1 - width + 1 - right), pen_min)
        upper = np.minimum(np.minimum(x0 + width - 1 - left, x1 - right), pen_max)
        return np.maximum(0, upper - lower + 1) * ((top == y0) & (bottom == y1))
