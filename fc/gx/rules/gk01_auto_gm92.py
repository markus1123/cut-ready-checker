from fc.core import Finding
from fc.gx.core import gx_rule
from shapely import affinity

R_MAX = 12.0       # mm: drilled / fitting holes (shelf pins, cams, dowels, screws); bigger openings are cut-outs
MIN_PART = 5000.0  # mm2: smaller loops are labels / offcuts
SHAPE_TOL = 0.005  # outlines that differ by < 0.5 % of their area are the same part (copies in the nest)
POS_TOL = 1.0      # mm: holes within 1 mm of each other after aligning the twins are the same hole (Minifix absorbs
                   # only +1 / -0.5 mm drilling error, a dowel joint less)
SHIFT = (2.0, 20.0)  # mm: a hole 2-20 mm from where its twin has it is the same hole drawn off position
MIN_HOLES = 2      # the twins must carry a hole pattern (>= 1 hole that still matches), not one stray mark


def _holes(p):
    """Drilled hole positions (centre, largest radius); concentric circles (pilot + countersink) are one hole."""
    out = []
    for f in p.features:
        if f.op != 'hole' or not f.r or f.r > R_MAX or f.geom is None: continue
        c = f.geom.centroid
        k = next((i for i, (q, r) in enumerate(out) if q.distance(c) < 0.5), None)
        if k is None: out.append((c, f.r))
        else: out[k] = (out[k][0], max(out[k][1], f.r))
    return out


def _poses(a, b):
    """Rigid moves (rotate 0/90/180/270, optionally mirrored) that put b's outline onto a's."""
    ca, cb = a.outer.centroid, b.outer.centroid
    out = []
    for mir in (False, True):
        ob = affinity.translate(b.outer, ca.x - cb.x, ca.y - cb.y)
        if mir: ob = affinity.scale(ob, -1, 1, origin=ca)
        for ang in (0, 90, 180, 270):
            r = affinity.rotate(ob, ang, origin=ca)
            if r.symmetric_difference(a.outer).area < SHAPE_TOL * a.outer.area:
                def f(pt, mir=mir, ang=ang):
                    q = affinity.translate(pt, ca.x - cb.x, ca.y - cb.y)
                    if mir: q = affinity.scale(q, -1, 1, origin=ca)
                    return affinity.rotate(q, ang, origin=ca)
                out.append(f)
    return out


def _compare(ha, hb, f):
    """Match a's holes to b's holes moved by pose f -> (n unmatched, (a hole, b hole) of the single mismatch or None)."""
    mb = [(f(c), r) for c, r in hb]
    used, miss = set(), []
    for c, rr in ha:
        j = next((k for k, (q, r) in enumerate(mb) if k not in used and q.distance(c) < POS_TOL and abs(r - rr) < 0.3), None)
        if j is None: miss.append((c, rr))
        else: used.add(j)
    rest = [mb[k] for k in range(len(mb)) if k not in used]
    if len(miss) == 1 and len(rest) == 1:
        return 1, (miss[0], rest[0])
    return len(miss) + len(rest), None


@gx_rule('GK01', 'A drilled hole on one of two identical parts off the position its twin has it at')
def check(g):
    """Identical parts in one cut file (left / right sides, pairs of rails, legs) are drilled for the same fitting
    or mating part, so their bores sit at the same place on every copy (mirrored for a handed pair). When all holes
    of two twins line up except ONE, and that hole sits 2-20 mm from where the twin has it (same diameter), the hole
    was nudged or snapped off position on one copy: its dowel, bolt or cam no longer meets the hole in the mating
    part - Minifix absorbs only +1 / -0.5 mm of drilling error, a dowel joint less. A copy that has an exact twin
    elsewhere in the file is taken as right; the odd one out is reported."""
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid]
    if len(parts) > 400: return
    hs = {id(p): _holes(p) for p in parts}
    for a in parts:
        ha = hs[id(a)]
        if len(ha) < MIN_HOLES: continue
        exact, near = False, None
        for b in parts:
            if a is b: continue
            hb = hs[id(b)]
            if len(hb) != len(ha): continue
            if abs(a.outer.area - b.outer.area) > SHAPE_TOL * a.outer.area: continue
            for f in _poses(a, b):
                n, mm = _compare(ha, hb, f)
                if n == 0: exact = True; break
                if mm is not None:
                    (ca, ra), (cb, rb) = mm
                    if abs(ra - rb) < 0.3 and SHIFT[0] <= ca.distance(cb) <= SHIFT[1] and near is None:
                        near = (ca, ra, ca.distance(cb))
            if exact: break
        if near and not exact:
            c, r, d = near
            yield Finding('GK01', 'error',
                          'the %.1f mm hole at (%.0f, %.0f) is %.1f mm off where an identical part in this file has it '
                          '(all its other %d holes match): the fitting / mating part will not line up'
                          % (2 * r, c.x, c.y, d, len(ha) - 1), a.key)
