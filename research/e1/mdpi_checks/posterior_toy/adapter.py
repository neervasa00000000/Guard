"""Translate toy data into the unchanged harness feasibility and score functions."""
import sys
from pathlib import Path

import numpy as np


def load(kit, review):
    global E, phase, d1, Geometry, Policy
    v = kit/"v5.7-ieee"
    sys.path[:0] = [str(kit/"results/e1-full/scripts"), str(v/"new_tests_posterior/scripts"),
                    str(v/"new_tests_review3/scripts"), str(review)]
    import e1lib as E
    import phase_exact as phase
    import d1_exact as d1
    from geometry import Geometry, Policy
    for name, (path, license_name, variation) in E.FONTS.items():
        E.FONTS[name] = (str(Path("/fonts")/Path(path).name), license_name, variation)


def geometry(raw, padding, fixed, line):
    g = np.asarray(raw, dtype=int).copy()
    if padding and line is not None:
        if fixed:
            geom = Geometry(g, line[0]+1, line[1]-1)
            left, right = geom.horizontal(Policy("pen-anchored", padding))
            g[:,0], g[:,2] = left+E.PAD, right-E.PAD
        else:
            g = E.bucket_transform(g, "DejaVuSans", 16, padding)
        g[:,1], g[:,3] = line[0]+E.PAD, line[1]-E.PAD
    elif padding:
        left = g[:,0].min() if fixed else g[:,0].copy()
        g[:,2] = left - (-(g[:,2]-left+2*E.PAD)//padding)*padding - 2*E.PAD
        g[:,0] = left
    return g


class Scorer:
    def __init__(self, geometry, prior, starts, baseline, grid, jitter, offsets):
        self.g = grid
        self.starts = starts
        self.shifts = [(dx, baseline+dy) for dx,dy in offsets]
        self.cell = E.Cell(geometry, ((0,0),)*4, jitter)
        self.jitter = jitter
        d1.J = jitter
        self.prior = np.array(prior,dtype=float)
        self.dictionary = dict(p=self.prior,m=np.ones(len(prior)),length=np.ones(len(prior),dtype=int))

    def evaluate(self, observation, collapse=False):
        start, boxes = observation
        if collapse:
            representative = []
            for (l,r,_,_),(dx,y) in zip(boxes,self.shifts):
                top = (y+self.cell.Thi[0])//self.g*self.g
                bottom = -(-(y+self.cell.Blo[0])//self.g)*self.g
                representative.append((l,r,top,bottom))
            boxes = representative
        shifts = [(dx+(start or 0),y) for dx,y in self.shifts]
        attacker = "A1" if start is not None else "A2"
        possible = self.cell.feasible(boxes, shifts, self.g, attacker)
        cell, grid = self.cell, self.g
        if self.jitter == 0:
            lo = self.starts[0] if start is None else start
            hi = self.starts[-1] if start is None else start
            for (l,r,t,b),(dx,_) in zip(boxes,self.shifts):
                lo = np.maximum(lo, np.maximum(l-cell.Lhi,r-grid+1-cell.Rhi)-dx)
                hi = np.minimum(hi, np.minimum(l+grid-1-cell.Llo,r-cell.Rlo)-dx)
            counts = np.where(possible,np.maximum(0,hi-lo+1),0)
        else:
            counts = np.zeros_like(self.prior,dtype=np.int64)
            starts = np.array(self.starts if start is None else [start])[:,None]
            draw = np.ones((len(starts),len(counts)),dtype=np.int64)
            for (l,r,t,b),(dx,y) in zip(boxes,self.shifts):
                x = starts+dx
                left, right = x+cell.Lhi, x+cell.Rlo
                top, bottom = y+cell.Thi, y+cell.Blo
                draw *= d1.cnt(left-l-grid+1,left-l)*d1.cnt(r-grid+1-right,r-right)
                if collapse:
                    draw *= (self.jitter+1)**2
                else:
                    draw *= d1.cnt(top-t-grid+1,top-t)*d1.cnt(b-grid+1-bottom,b-bottom)
            counts = draw.sum(axis=0)
            assert not np.any((counts>0)&~possible)
        supported = np.flatnonzero(counts)
        assert supported.size
        truth = int(supported[0])
        weights = self.prior*counts
        h = phase.scores(self.dictionary,weights,truth,1)[3]
        if start is not None and not self.jitter:
            flat = E.metrics(self.dictionary,possible,truth,1,np.log2(self.prior))["resid_bits"]
            assert abs(h-flat) < 1e-9
        return counts, h
