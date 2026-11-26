import math
from collections import Counter
from fc.core import Finding
from fc.gx.core import gx_rule

LO, HI = 1.5, 6.0     # degrees off square: below 1.5 is drawing noise / ply tolerance, above 6 is a deliberate splay
MIN_EDGE = 40.0       # mm: straight outline edges at least this long are reference directions


def _axes(poly):
    r = poly.minimum_rotated_rectangle
    if r.geom_type != 'Polygon':
        return None
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    if a >= b:
        ang = math.degrees(math.atan2(c[1][1] - c[0][1], c[1][0] - c[0][0]))
    else:
        ang = math.degrees(math.atan2(c[2][1] - c[1][1], c[2][0] - c[1][0]))
    return r, min(a, b), max(a, b), ang


def _off(a, b):
    x = (a - b) % 90.0
    return min(x, 90.0 - x)


def _refs(p, skip):
    """Directions a slot in this part could be square to: long straight outline edges and the other slots."""
    out = []
    pts = list(p.outer.exterior.coords)
    for a, b in zip(pts, pts[1:]):
        if math.dist(a, b) >= MIN_EDGE:
            out.append(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))
    for i in p.inner:
        if i is skip or i.area < 50:
            continue
        ax = _axes(i)
        if ax and ax[2] >= 1.5 * ax[1] and i.area > 0.8 * ax[0].area:
            out.append(ax[3])
    return out


@gx_rule('GF01', 'A lone sheet slot drawn a few degrees off square')
def check(g):
    """A slot that receives another sheet must be square to the direction the mating part comes in: the mating
    part is a flat sheet, so a slot rotated by a few degrees makes it enter skewed - 4 degrees across an 18 mm sheet
    is ~1.3 mm of misalignment, so a press-fit joint binds or splits the ply and the assembly leans (Opendesk /
    WikiHouse slot-joint guidance: slots square to the mating sheet, sheet + small clearance). Deliberate angled
    slots exist (splayed legs, reclined backs), but they are repeated on every symmetric copy - left and right sides,
    pairs of legs - and are usually steeper. A slot 1.5-6 degrees off every long straight edge and every other slot of
    its part, whose skew is found on no other slot in the file, is a rotate / snap error in CAD.
    Slot = straight rectangular through opening 0.9-1.35 x sheet thickness wide and >= 1.5x as long."""
    th = g.thickness or g.thickness_est
    if not th:
        return
    cand = []
    for p in g.parts:
        for i in p.inner:
            if i.area < 50:
                continue
            ax = _axes(i)
            if not ax:
                continue
            r, w, L, ang = ax
            if not (0.9 * th <= w <= 1.35 * th and L >= 1.5 * w and i.area > 0.8 * r.area):
                continue
            R = _refs(p, i)
            if not R:
                continue
            cand.append((p, w, min(_off(ang, x) for x in R)))
    seen = Counter(round(s, 1) for _, _, s in cand if s > 0.5)
    for p, w, s in cand:
        if LO <= s <= HI and seen[round(s, 1)] == 1:
            yield Finding('GF01', 'error',
                          'slot %.1f mm wide drawn %.1f degrees off square to its part and every other slot, and no '
                          'other slot in the file has that angle - the mating sheet enters skewed and the joint binds'
                          % (w, s), p.key)
