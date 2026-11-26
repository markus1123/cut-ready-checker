import math
from shapely import affinity
from fc.core import Finding
from fc.gx.core import gx_rule

MIN_PART = 10000.0   # mm2: panels, not trim
SAME = 0.3           # mm: mean outline deviation allowed (symmetric difference / perimeter): the same part, not a
                     # slightly bigger or smaller sibling (drawer bottoms for two drawer sizes)
MATCH = 0.5          # mm: openings within this of each other are the same opening
SHIFT = (2.0, 40.0)  # mm: a consistent offset in this range is a misregistration (a press-fit slot tolerates ~0.5)
MAX_OPEN = 300       # parts with more openings are perforated / decorative patterns: skipped for speed


def _openings(p):
    return [i.centroid for i in p.inner if i.area > 20][:MAX_OPEN + 1]


def _has_slot(p):
    """Does the part have a slot-shaped opening (straight, >= 3 mm wide, >= 1.5x as long): a joint for a mating part."""
    for i in p.inner:
        if i.area <= 20:
            continue
        r = i.minimum_rotated_rectangle
        if r.geom_type != 'Polygon':
            continue
        c = list(r.exterior.coords)
        w, L = sorted((math.dist(c[0], c[1]), math.dist(c[1], c[2])))
        if w >= 3 and L >= 1.5 * w and i.area > 0.7 * r.area:
            return True
    return False


def _transforms(a, b):
    """Rigid / mirrored placements of b's outline onto a's: yields functions mapping b's points into a's frame."""
    ca, cb = a.outer.centroid, b.outer.centroid
    base = affinity.translate(b.outer, ca.x - cb.x, ca.y - cb.y)
    for mirror in (False, True):
        m = affinity.scale(base, -1, 1, origin=ca) if mirror else base
        for ang in (0, 90, 180, 270):
            o = affinity.rotate(m, ang, origin=ca)
            if o.symmetric_difference(a.outer).area < SAME * a.outer.length:
                def f(pt, mirror=mirror, ang=ang):
                    q = affinity.translate(pt, ca.x - cb.x, ca.y - cb.y)
                    if mirror: q = affinity.scale(q, -1, 1, origin=ca)
                    return affinity.rotate(q, ang, origin=ca)
                yield f


def _offset(pa, pb):
    """pa, pb: matched opening centres. -> constant offset vector length if every opening of pa sits at the same
    offset from one of pb (and not at 0), else None / 0."""
    if len(pa) != len(pb) or not pa:
        return None
    d = [(q.x - p.x, q.y - p.y) for p in pa for q in [min(pb, key=lambda q: q.distance(p))]]
    if all(math.hypot(*v) <= MATCH for v in d):
        return 0.0
    # try the offset of the first opening against every opening of the twin
    for q in pb:
        dx, dy = q.x - pa[0].x, q.y - pa[0].y
        if all(min(math.hypot(r.x - p.x - dx, r.y - p.y - dy) for r in pb) <= MATCH for p in pa):
            return math.hypot(dx, dy)
    return None


@gx_rule('GF07', 'Identical parts with all openings of one shifted against its outline')
def check(g):
    """Identical parts (same outline, possibly turned or mirrored) carry the same openings for the same hardware
    and mating parts. When one copy has EVERY hole and slot shifted by one and the same 2-40 mm offset relative
    to its outline, the outline was moved or nested without them - the openings were on a locked, hidden or
    separate layer, or not grouped with it (Vectric nesting with locked layers; SketchUp / Inkscape loose geometry
    on export). That copy is cut with every opening out of place: screws, dowels and the parts in its slots do not
    line up, and the assembly does not go together. Twins whose openings differ in pattern (a left and a right
    side with different hardware) are not judged; only a pure constant shift of the whole set is. Only parts with at least
    one slot for a mating part are judged: a slot joint tolerates ~0.5 mm, whereas round holes for loose-fit pulls /
    screws are legitimately placed per copy (built Fellesverkstedet drawer bottoms move them up to ~8 mm)."""
    big = [p for p in g.parts if p.outer.area >= MIN_PART and p.outer.is_valid]
    done = set()
    for x, a in enumerate(big):
        oa = _openings(a)
        if len(oa) < 2 or len(oa) > MAX_OPEN or not _has_slot(a):
            continue
        for b in big[x + 1:]:
            if abs(a.outer.area - b.outer.area) > SAME * a.outer.length:
                continue
            ob = _openings(b)
            if len(ob) != len(oa):
                continue
            offs = []
            for f in _transforms(a, b):
                offs.append(_offset(oa, [f(q) for q in ob]))
            if not offs or 0.0 in offs:
                continue
            s = [o for o in offs if o is not None and SHIFT[0] <= o <= SHIFT[1]]
            if s and (a.key, b.key) not in done:
                done.add((a.key, b.key))
                yield Finding('GF07', 'error',
                              'all %d openings of this part sit %.1f mm off, against its identical twin part: the '
                              'outline was moved without its holes / slots - nothing lines up' % (len(oa), min(s)), b.key)
                yield Finding('GF07', 'error',
                              'twin of a part whose %d openings are all %.1f mm off: one of the two is misregistered'
                              % (len(oa), min(s)), a.key)
