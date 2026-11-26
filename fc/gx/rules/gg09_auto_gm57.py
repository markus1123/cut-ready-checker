import math
from fc.core import Finding
from fc.gx.core import gx_rule
from shapely import affinity

MIN_PART = 5000.0   # mm2
SHAPE_TOL = 0.005   # outlines differing by < 0.5 % of their area are copies of one part
POS_TOL = 1.0       # mm: the same feature on the twin, centre for centre
AREA_TOL = 0.05     # ... and the same size within 5 %
MIN_FEAT = 100.0    # mm2: pockets / openings smaller than this are marks; drilled holes are GG01's job
R_HOLE = 12.0       # mm: round features up to this radius are drilled holes, not slots / housings
MIN_HOUSING = 300.0 # mm2: a housing that takes a part; smaller pockets are logos / labels (built files put those on one copy)
SHALLOW = 3.0       # mm: engraved marks, not housings
MIN_TWINS = 2       # the housing is on 2+ other copies: an odd one out, not a deliberate left/right or top/bottom variant


def _poses(a, b):
    ca, cb = a.outer.centroid, b.outer.centroid
    for mir in (False, True):
        ob = affinity.translate(b.outer, ca.x - cb.x, ca.y - cb.y)
        if mir: ob = affinity.scale(ob, -1, 1, origin=ca)
        for ang in (0, 90, 180, 270):
            if affinity.rotate(ob, ang, origin=ca).symmetric_difference(a.outer).area < SHAPE_TOL * a.outer.area:
                def f(x, mir=mir, ang=ang):
                    y = affinity.translate(x, ca.x - cb.x, ca.y - cb.y)
                    if mir: y = affinity.scale(y, -1, 1, origin=ca)
                    return affinity.rotate(y, ang, origin=ca)
                yield f


def _slotlike(i, th):
    r = i.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return False
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    w, L = min(a, b), max(a, b)
    return 0.9 * th <= w <= 1.4 * th and L >= 1.5 * w and i.area > 0.75 * r.area


def _feats(p, th):
    """(kind, geometry, judged) for every pocket and through opening of the part (no drilled holes). 'judged' marks
    the ones that take a mating part: housings (pockets > 3 mm deep, >= 300 mm2) and slots one sheet thick."""
    hole = {id(f.geom) for f in p.features if f.op == 'hole' and f.r and f.r <= R_HOLE}
    out = [('pocket', f.geom, f.geom.area >= MIN_HOUSING and not (f.depth is not None and f.depth <= SHALLOW))
           for f in p.features if f.op == 'pocket' and f.geom is not None and f.geom.area > MIN_FEAT
           and not (f.r and f.r <= R_HOLE)]
    out += [('opening', i, False) for i in p.inner if i.area > MIN_FEAT and id(i) not in hole]
    return out


def _match(fa, fb):
    """fb (moved onto a) has exactly one feature more than fa, and every feature of fa has its twin in fb."""
    used = set()
    for k, x, _ in fa:
        c = x.centroid
        j = next((n for n, (kb, y, _) in enumerate(fb) if n not in used and kb == k and y.centroid.distance(c) < POS_TOL
                  and abs(y.area - x.area) < AREA_TOL * x.area), None)
        if j is None: return None
        used.add(j)
    rest = [fb[n] for n in range(len(fb)) if n not in used]
    return rest[0] if len(rest) == 1 and rest[0][2] else None


@gx_rule('GG09', 'A housing (pocket) missing on one of two identical parts')
def check(g):
    """Copies of a part (pairs of sides, legs, rails) carry the same housings and the same slots: each housing takes a
    shelf / back / fitting, each slot a mating sheet or tab (Opendesk / AtFAB slot-together assembly guides). When a
    part is identical to two or more others in the file - same outline, every housing and slot it has matching one
    on each of them - but they all have exactly one housing more (the odd copy out; a 1 + 1 pair can be a
    deliberate variant, the Opendesk Layout table has such pairs), that feature was lost on export (layer turned off, deleted
    as a 'duplicate'): the part it should receive has nowhere to go and the kit cannot be assembled without
    recutting. Only the missing feature's kind that reliably takes a part is judged - housings (pockets deeper than
    3 mm, >= 300 mm2); openings must still match between the twins, but a missing slot or cut-out is not flagged:
    built files put logos, labels, handle cut-outs and even an extra slot (Opendesk Layout table rail) on one copy. Twins are matched by
    outline (rotation and mirroring allowed); drilled holes are left to GG01."""
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid]
    if len(parts) > 300: return
    th = g.thickness or g.thickness_est
    F = {id(p): _feats(p, th) for p in parts}
    for a in parts:
        fa = F[id(a)]
        hits = []
        for b in parts:
            fb = F[id(b)]
            if a is b or len(fb) != len(fa) + 1 or len(fb) < 2: continue
            if abs(a.outer.area - b.outer.area) > SHAPE_TOL * a.outer.area: continue
            for f in _poses(a, b):
                h = _match(fa, [(k, f(y), j) for k, y, j in fb])
                if h: hits.append(h); break
        hit = hits[0] if len(hits) >= MIN_TWINS else None
        if hit:
            k, y, _ = hit
            what = 'housing (pocket)' if k == 'pocket' else 'through slot / opening'
            yield Finding('GG09', 'error', 'an identical part in this file has a %s here (%.0f mm2) that this copy '
                          'lacks, all its other features match: lost on export - its mating part has nowhere to go'
                          % (what, y.area), a.key)
