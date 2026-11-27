from fc.core import Finding
from fc.gx.core import gx_rule
from shapely import affinity

R_HOLE = 12.0      # mm: round openings up to this radius are drilled holes (rule GK01 compares those)
MIN_PART = 5000.0  # mm2: smaller loops are labels / offcuts
MIN_OPEN = 150.0   # mm2: openings smaller than this are marks / pilot holes
SHAPE_TOL = 0.005  # outlines differing by < 0.5 % of their area are the same part (copies in the nest)
POS_TOL = 1.0      # mm: openings whose centres land within 1 mm after aligning the twins are the same opening
SHIFT = (3.0, 20.0)  # mm: an opening 3-20 mm from where its twin has it is the same slot drawn off position;
                     # press-fit slots have 0-0.5 mm clearance, but loose-fit slots / hand holds absorb ~2 mm, and a
                     # tab 3 mm off its slot does not enter either kind


def _openings(p):
    """Through openings that are not drilled holes -> list of (centre, area)."""
    hole = {id(f.geom) for f in p.features if f.op == 'hole' and f.r and f.r <= R_HOLE}
    return [(i.centroid, i.area) for i in p.inner if i.area >= MIN_OPEN and id(i) not in hole]


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


def _same(x, y):
    return abs(x - y) <= 0.01 * max(x, y)


def _compare(oa, ob, f):
    mb = [(f(c), ar) for c, ar in ob]
    used, miss = set(), []
    for c, ar in oa:
        j = next((k for k, (q, r) in enumerate(mb) if k not in used and q.distance(c) < POS_TOL and _same(r, ar)), None)
        if j is None: miss.append((c, ar))
        else: used.add(j)
    rest = [mb[k] for k in range(len(mb)) if k not in used]
    if len(miss) == 1 and len(rest) == 1:
        return 1, (miss[0], rest[0])
    return len(miss) + len(rest), None


@gx_rule('GK05', 'A slot / cut-out on one of two identical parts off the position its twin has it at')
def check(g):
    """Identical parts in one cut file (pairs of sides, rails, legs) take the same tabs, rails and mating sheets, so
    their slots and cut-outs sit at the same place on every copy (mirrored for a handed pair). When all openings of
    two twins line up except ONE, and that one is the same shape and size but 3-20 mm from where the twin has it,
    the slot was nudged or snapped off position on one copy: press-fit slots are drawn with 0-0.5 mm clearance, so
    the tab or sheet that goes through it no longer lines up and the frame cannot be assembled square. A copy that
    has an exact twin elsewhere in the file is taken as right; the odd one out is reported."""
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid]
    if len(parts) > 400: return
    op = {id(p): _openings(p) for p in parts}
    for a in parts:
        oa = op[id(a)]
        if not oa: continue
        exact, near = False, None
        for b in parts:
            if a is b: continue
            ob = op[id(b)]
            if len(ob) != len(oa): continue
            if abs(a.outer.area - b.outer.area) > SHAPE_TOL * a.outer.area: continue
            for f in _poses(a, b):
                n, mm = _compare(oa, ob, f)
                if n == 0: exact = True; break
                if mm is not None:
                    (ca, ra), (cb, rb) = mm
                    if _same(ra, rb) and SHIFT[0] <= ca.distance(cb) <= SHIFT[1] and near is None:
                        near = (ca, ca.distance(cb))
            if exact: break
        if near and not exact:
            c, d = near
            yield Finding('GK05', 'error',
                          'the opening at (%.0f, %.0f) is %.1f mm off where an identical part in this file has it (all '
                          'its other %d openings match): the tab / sheet that goes through it will not line up'
                          % (c.x, c.y, d, len(oa) - 1), a.key)
