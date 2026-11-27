"""GJ04: a part that is an exact copy of another part, features and all, scaled up by a few per cent."""
import math
from shapely import affinity
from fc.core import Finding
from fc.gx.core import gx_rule

MIN_PART = 5000.0           # mm2: smaller loops are labels / offcuts
K_RANGE = (1.02, 1.15)      # linear scale between the two copies: 72/96, 90/96 dpi and %-scale slips; above, graded sizes
SHAPE_TOL = 0.005           # outlines (after scaling) differing by < 0.5 % of their area are the same shape
POS_TOL = 1.0               # mm: a feature of the scaled-down copy lands within 1 mm of its twin's
MIN_FEAT = 1                # the part must carry a hole / opening / pocket: without one, scaled and re-sized look alike


def _feats(p):
    out = [i.centroid for i in p.inner if i.area > 5]
    out += [f.geom.centroid for f in p.features if f.geom is not None and not f.geom.is_empty and f.geom.area > 0.5
            and not any(f.geom is i for i in p.inner)]
    return out


def _sizes(p):
    return sorted([i.area for i in p.inner if i.area > 5] +
                  [f.geom.area for f in p.features if f.geom is not None and not f.geom.is_empty and f.geom.area > 0.5
                   and not any(f.geom is i for i in p.inner)])


@gx_rule('GJ04', 'A part is a copy of another part scaled a few per cent, holes and slots included')
def check(g):
    """Copies of a part (left / right sides, pairs of legs) are the same size. A copy brought in from an SVG / PDF
    at the wrong resolution (Inkscape <= 0.91 used 90 px/in, everything else 96: x1.067; 72 pt vs 96 px: x1.333) or
    scaled by a slip of the scale command comes out a few per cent too large while the rest of the file is right:
    it no longer matches its mating parts, its slots and holes are off their partners. Real size variants of a part
    (a deeper shelf, a taller side) keep their hardware: the holes, slots and pockets stay the bore / sheet size.
    So when a part is the exact image of another part scaled 1.02-1.15x - outline AND every hole, slot and pocket,
    positions and sizes (by area, k^2) - it is that scaling error, not a design variant (Ponoko / SendCutSend file
    prep: check scale after import; Inkscape 0.92 release notes on the 90 -> 96 dpi change)."""
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid]
    if len(parts) > 300:
        return
    F = {id(p): _feats(p) for p in parts}
    S = {id(p): _sizes(p) for p in parts}
    done = set()
    for a in parts:                      # a = the larger copy
        for b in parts:
            if a is b or id(a) in done or len(F[id(a)]) != len(F[id(b)]) or len(F[id(a)]) < MIN_FEAT:
                continue
            k2 = a.outer.area / b.outer.area
            if not K_RANGE[0] ** 2 <= k2 <= K_RANGE[1] ** 2:
                continue
            k = math.sqrt(k2)
            sa, sb = S[id(a)], S[id(b)]
            if any(abs(x - y * k2) > 0.06 * x + 1 for x, y in zip(sa, sb)):
                continue                 # hardware not scaled with the outline: a real size variant
            ca, cb = a.outer.centroid, b.outer.centroid
            hit = False
            for mir in (False, True):
                ob = affinity.scale(affinity.translate(b.outer, ca.x - cb.x, ca.y - cb.y), k, k, origin=ca)
                if mir: ob = affinity.scale(ob, -1, 1, origin=ca)
                for ang in (0, 90, 180, 270):
                    try:
                        if affinity.rotate(ob, ang, origin=ca).symmetric_difference(a.outer).area >= SHAPE_TOL * a.outer.area:
                            continue
                    except Exception:
                        continue
                    def T(pt, mir=mir, ang=ang):
                        q = affinity.scale(affinity.translate(pt, ca.x - cb.x, ca.y - cb.y), k, k, origin=ca)
                        if mir: q = affinity.scale(q, -1, 1, origin=ca)
                        return affinity.rotate(q, ang, origin=ca)
                    fb = [T(c) for c in F[id(b)]]
                    if all(any(c.distance(q) < POS_TOL for q in fb) for c in F[id(a)]):
                        hit = True
                        break
                if hit:
                    break
            if hit:
                done.add(id(a))
                yield Finding('GJ04', 'error', 'this part is another part of the file scaled %.3fx - outline, holes '
                              'and slots alike (a 90/96 dpi or 72/96 import, or a scale slip): it will not match its '
                              'mating parts' % k, a.key)
