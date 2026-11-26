from fc.core import Finding
from fc.gx.core import gx_rule
from shapely import affinity
from shapely.geometry import Point

R_MAX = 12.0       # mm: drilled / fitting holes (shelf pins, cams, dowels, screws); bigger openings are cut-outs
MIN_PART = 5000.0  # mm2: smaller loops are labels / offcuts
SHAPE_TOL = 0.005  # outlines that differ by < 0.5 % of their area are the same part (copies in the nest)
POS_TOL = 1.0      # mm: holes that land within 1 mm of each other after aligning the twins are the same hole
MIN_HOLES = 2      # the twin must carry a real hole pattern, not one stray mark


def _holes(p):
    """Drilled hole POSITIONS (centre, largest radius): concentric circles (pilot + countersink / counterbore, as
    AtFAB files draw them) are one hole."""
    out = []
    for f in p.features:
        if f.op != 'hole' or not f.r or f.r > R_MAX: continue
        c = f.geom.centroid
        k = next((i for i, (q, r) in enumerate(out) if q.distance(c) < 0.5), None)
        if k is None: out.append((c, f.r))
        else: out[k] = (out[k][0], max(out[k][1], f.r))
    return out


def _poses(a, b):
    """Rigid moves (rotate 0/90/180/270, optionally mirrored) that put b's outline onto a's: list of fn(Point)->Point."""
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


@gx_rule('GG01', 'A drilled hole missing on one of two identical parts')
def check(g):
    """Identical parts in one cut file (left / right sides, pairs of legs, shelves) are drilled for the same hardware:
    System 32 shelf-pin rows, cam / dowel / confirmat bores sit at the same place on each copy (Hettich, Hafele: each
    panel of a pair carries the same bores, mirrored for a handed pair). When every drilled hole of a part lines up
    with a hole of its twin, but the twin has exactly ONE hole more, a hole was lost on export (frozen / hidden layer,
    exploded block): the screw, dowel or pin for that copy has nowhere to go and the part is drilled by hand or recut.
    Twins are matched by outline (rotation and mirroring allowed) and the hole positions compared after aligning
    them; concentric circles (pilot + countersink) count as one hole."""
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid]
    if len(parts) > 400: return
    hs = {id(p): _holes(p) for p in parts}
    flagged = set()
    for a in parts:
        ha = hs[id(a)]
        for b in parts:
            if a is b or id(a) in flagged: continue
            hb = hs[id(b)]
            if len(hb) != len(ha) + 1 or len(hb) < MIN_HOLES: continue
            if abs(a.outer.area - b.outer.area) > SHAPE_TOL * a.outer.area: continue
            for f in _poses(a, b):
                mb = [(f(c), r) for c, r in hb]
                used, ok = set(), True
                for c, rr in ha:
                    j = next((k for k, (q, r) in enumerate(mb) if k not in used and q.distance(c) < POS_TOL and abs(r - rr) < 0.3), None)
                    if j is None: ok = False; break
                    used.add(j)
                if ok:
                    miss = [mb[k] for k in range(len(mb)) if k not in used][0]
                    flagged.add(id(a))
                    yield Finding('GG01', 'error',
                                  'an identical part in this file has a %.1f mm hole here at (%.0f, %.0f) that this copy '
                                  'lacks (all its other %d holes match): a hole lost on export - the fitting has '
                                  'nowhere to go' % (2 * miss[1], miss[0].x, miss[0].y, len(ha)), a.key)
                    break
