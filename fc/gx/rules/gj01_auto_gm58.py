"""GJ01: a through slot missing on one copy of a part that two or more identical copies all carry."""
import math
from fc.core import Finding
from fc.gx.core import gx_rule
from shapely import affinity

MIN_PART = 5000.0   # mm2: smaller loops are labels / offcuts
SHAPE_TOL = 0.005   # outlines differing by < 0.5 % of their area are copies of one part
POS_TOL = 1.0       # mm: the same feature on the twin, centre for centre
AREA_TOL = 0.05     # ... and the same size within 5 %
MIN_FEAT = 100.0    # mm2: smaller openings are marks; drilled holes are GG01's job
R_HOLE = 12.0       # mm: round features up to this radius are drilled holes
MIN_TWINS = 2       # copies that carry the slot, and more of them than copies without it: the odd one out


def _poses(a, b):
    ca, cb = a.outer.centroid, b.outer.centroid
    for mir in (False, True):
        ob = affinity.translate(b.outer, ca.x - cb.x, ca.y - cb.y)
        if mir: ob = affinity.scale(ob, -1, 1, origin=ca)
        for ang in (0, 90, 180, 270):
            try:
                d = affinity.rotate(ob, ang, origin=ca).symmetric_difference(a.outer).area
            except Exception:       # GEOS topology error on a near-degenerate outline: not a clean copy
                continue
            if d < SHAPE_TOL * a.outer.area:
                def f(x, mir=mir, ang=ang):
                    y = affinity.translate(x, ca.x - cb.x, ca.y - cb.y)
                    if mir: y = affinity.scale(y, -1, 1, origin=ca)
                    return affinity.rotate(y, ang, origin=ca)
                yield f


def _slot(i, th):
    """A through opening shaped like a slot for a mating sheet: narrow side about one sheet thick, long and straight."""
    if not th: return False
    r = i.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return False
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    w, L = min(a, b), max(a, b)
    return 0.9 * th <= w <= 1.4 * th and L >= 1.5 * w and i.area > 0.75 * r.area


def _feats(p, th):
    hole = {id(f.geom) for f in p.features if f.op == 'hole' and f.r and f.r <= R_HOLE}
    out = [('pocket', f.geom, False) for f in p.features if f.op == 'pocket' and f.geom is not None
           and f.geom.area > MIN_FEAT and not (f.r and f.r <= R_HOLE)]
    out += [('opening', i, _slot(i, th)) for i in p.inner if i.area > MIN_FEAT and id(i) not in hole]
    return out


def _match(fa, fb):
    used = set()
    for k, x, _ in fa:
        c = x.centroid
        j = next((n for n, (kb, y, _) in enumerate(fb) if n not in used and kb == k and y.centroid.distance(c) < POS_TOL
                  and abs(y.area - x.area) < AREA_TOL * x.area), None)
        if j is None: return None
        used.add(j)
    rest = [fb[n] for n in range(len(fb)) if n not in used]
    return rest[0] if len(rest) == 1 and rest[0][2] else None


def _same(fa, fb):
    """fb (moved onto a) has the same features as fa."""
    used = set()
    for k, x, _ in fa:
        c = x.centroid
        j = next((n for n, (kb, y, _) in enumerate(fb) if n not in used and kb == k and y.centroid.distance(c) < POS_TOL
                  and abs(y.area - x.area) < AREA_TOL * x.area), None)
        if j is None: return False
        used.add(j)
    return True


@gx_rule('GJ01', 'A through slot missing on one of several identical parts')
def check(g):
    """In slot-together furniture every slot receives a mating sheet or tab (Opendesk / AtFAB slot-together assembly
    guides, WikiHouse design guide). When a part is identical to two or more other parts in the file - same outline
    (rotation / mirroring allowed), every pocket and opening it has matching one on each of them - but all of them
    carry exactly one sheet-thick slot more - and the copies with the slot outnumber the copies without it - that slot was lost on export (frozen layer, deleted as a duplicate):
    the mating part has nowhere to go and the kit does not assemble. A 1 + 1 pair or an even split is not judged
    (a deliberate variant: the Opendesk Layout table has two rails with a middle slot and two without); slots are openings 0.9-1.4x the sheet thick and
    >= 1.5x as long as wide."""
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid]
    if len(parts) > 300: return
    th = g.thickness or g.thickness_est
    if not th: return
    F = {id(p): _feats(p, th) for p in parts}
    for a in parts:
        fa = F[id(a)]
        hits, same = [], 1
        for b in parts:
            fb = F[id(b)]
            if a is not b and len(fb) == len(fa) and abs(a.outer.area - b.outer.area) <= SHAPE_TOL * a.outer.area \
                    and any(_same(fa, [(k, f(y), j) for k, y, j in fb]) for f in _poses(a, b)):
                same += 1; continue
            if a is b or len(fb) != len(fa) + 1: continue
            if abs(a.outer.area - b.outer.area) > SHAPE_TOL * a.outer.area: continue
            for f in _poses(a, b):
                h = _match(fa, [(k, f(y), j) for k, y, j in fb])
                if h: hits.append(h); break
        if len(hits) >= MIN_TWINS and len(hits) > same:
            y = hits[0][1]
            yield Finding('GJ01', 'error', '%d identical parts in this file have a %.0f mm2 through slot here that this '
                          'copy lacks, all its other features match: lost on export - the mating sheet has nowhere to go'
                          % (len(hits), y.area), a.key)
