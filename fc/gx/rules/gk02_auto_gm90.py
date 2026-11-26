import math
from fc.core import Finding
from fc.gx.core import gx_rule
from shapely import affinity
from shapely.geometry import box

MIN_PART = 5000.0     # mm2: smaller loops are labels / offcuts
W_TOL = 0.3           # mm: twins have the same width (a cut part is accurate to ~0.1-0.2 mm)
DL = (2.5, 8.0)       # mm: one copy 2.5-8 mm shorter than the other = a trimmed / mis-edited copy, not another part;
                      # up to ~2 mm can be a deliberate fit allowance (a copy that sits between two others / in a
                      # rebate gets its clearance taken off one end)
SAME = 0.5            # mm: features (holes / openings) within 0.5 mm after aligning are the same feature


def _axes(poly):
    r = poly.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return None
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    ang = math.degrees(math.atan2(c[1][1] - c[0][1], c[1][0] - c[0][0])) if a >= b else \
        math.degrees(math.atan2(c[2][1] - c[1][1], c[2][0] - c[1][0]))
    return min(a, b), max(a, b), ang


def _norm(p):
    """Part -> (outline, feature centroids, W, L) rotated so the long side runs along x, origin at the bbox centre-left."""
    ax = _axes(p.outer)
    if ax is None: return None
    W, L, ang = ax
    c = p.outer.centroid
    o = affinity.rotate(p.outer, -ang, origin=c)
    pts = [affinity.rotate(i.centroid, -ang, origin=c) for i in p.inner] + \
          [affinity.rotate(f.geom.centroid, -ang, origin=c) for f in p.features if f.geom is not None and f.geom not in p.inner]
    return o, pts, W, L


def _place(o, pts, flipx, flipy, end):
    """Flip, then translate so the chosen end (0 = left, 1 = right) of the bbox is at x = 0 and the bbox is centred on y = 0."""
    minx, miny, maxx, maxy = o.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    sx, sy = (-1 if flipx else 1), (-1 if flipy else 1)
    o = affinity.scale(o, sx, sy, origin=(cx, cy))
    pts = [affinity.scale(q, sx, sy, origin=(cx, cy)) for q in pts]
    minx, miny, maxx, maxy = o.bounds
    dx = -(minx if end == 0 else maxx); dy = -(miny + maxy) / 2
    return affinity.translate(o, dx, dy), [affinity.translate(q, dx, dy) for q in pts]


def _complex(o, pts):
    """Enough shape to tell 'same part, one end trimmed' from 'two different plain panels': a profiled outline
    (notches, tapers, curves) or a feature pattern."""
    s = o.simplify(0.5)
    return len(s.exterior.coords) > 6 or o.area < 0.97 * o.minimum_rotated_rectangle.area or len(pts) >= 2


@gx_rule('GK02', 'One of two identical parts drawn a few mm shorter at one end than its twin')
def check(g):
    """Paired parts (left / right sides, front / back rails, legs) carry the same load and meet the same mating parts,
    so their copies in a cut file are identical. When two parts have the same width, the same profile and the same
    holes / openings, but one is 2.5-8 mm shorter and is exactly the longer one cut off straight across ONE end, one copy was
    trimmed or edited after copying (or its end snapped to the wrong line): a cabinet or table built from them rocks,
    its shelves and top slope, and slot-together joints / dowels on the mating parts stop lining up (a cut part is
    accurate to ~0.2 mm; fit allowances taken off one copy stay at ~2 mm or less). Plain rectangles without features are
    not judged: two panels 3 mm apart in length can be two different parts. A copy that has an exact twin elsewhere
    in the file is taken as right."""
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid]
    if len(parts) > 400: return
    N = {}
    for p in parts:
        n = _norm(p)
        if n and n[3] >= n[2] + 20: N[id(p)] = n
    ps = [p for p in parts if id(p) in N]
    for a in ps:
        oa, pa, Wa, La = N[id(a)]
        if not _complex(oa, pa): continue
        exact = near = None
        for b in ps:
            if a is b: continue
            ob, pb, Wb, Lb = N[id(b)]
            if abs(Wa - Wb) > W_TOL or len(pa) != len(pb): continue
            dl = abs(Lb - La)
            if dl < 0.3 and abs(a.outer.area - b.outer.area) < 0.005 * a.outer.area:
                exact = True; break
            if not (DL[0] <= dl <= DL[1]): continue
            # align both at the SAME end (the untouched one); the difference must be a strip across the other end
            A0 = {e: _place(oa, pa, False, False, e) for e in (0, 1)}
            hit = False
            for fx in (False, True):
                for fy in (False, True):
                    for e in (0, 1):
                        A, Ap = A0[e]
                        B, Bp = _place(ob, pb, fx, fy, e)
                        # the shorter copy must be EXACTLY the longer one cut off straight across at its end
                        lo, hi = (A, B) if La < Lb else (B, A)
                        x0, y0, x1, y1 = lo.bounds
                        cut = hi.intersection(box(x0, y0 - 5, x1, y1 + 5))
                        if cut.symmetric_difference(lo).area > 0.001 * lo.area + 2.0: continue
                        if any(min((q.distance(r) for r in Bp), default=99) > SAME for q in Ap): continue
                        hit = True; break
                    if hit: break
                if hit: break
            if hit and near is None: near = (dl, La < Lb)
        if near and not exact:
            dl, shorter = near
            yield Finding('GK02', 'error',
                          'this part is %.1f mm %s than an otherwise identical part in this file (same width, profile '
                          'and holes; the difference is one end): one copy was trimmed / edited - a pair that should '
                          'match will not, so the piece rocks or its joints do not line up'
                          % (dl, 'shorter' if shorter else 'longer'), a.key)
