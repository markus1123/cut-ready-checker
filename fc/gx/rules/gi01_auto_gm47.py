"""GI01: a through opening with exactly the shape of the file's pockets / housings - a housing on the cut layer."""
import math
from fc.core import Finding
from fc.gx.core import gx_rule

MIN_AREA = 100.0    # mm2: smaller loops are marks / drill points, not housings
LEN_TOL = 0.5       # mm: width / length agree within this (export rounding; far below any fit clearance)
AREA_TOL = 0.03     # relative area difference still 'the same shape'


def _sig(poly):
    r = poly.minimum_rotated_rectangle
    if r.geom_type != 'Polygon':
        return None
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return min(a, b), max(a, b), poly.area


def _same(s, q):
    return abs(s[0] - q[0]) <= LEN_TOL and abs(s[1] - q[1]) <= LEN_TOL and \
        abs(s[2] - q[2]) <= AREA_TOL * max(s[2], q[2])


@gx_rule('GI01', 'Through opening with the exact shape of a pocket / housing in the same file (housing on the cut layer)')
def check(g):
    """A housing, recess or rebate is a POCKET: it stops part-way so the shelf, back panel or fitting has a floor to
    sit on. When a file machines some housings as pockets and has a through opening of exactly the same size and
    shape (width and length within 0.5 mm, area within 3 %), that opening is one of those housings put on the
    profile / through-cut layer: CAM cuts it out of the sheet, the panel gets a hole where it needed a housing, and a
    long housing nearly cuts the panel in two. Openings that really are through-slots for tabs are a different size
    from the file's pockets (a tab slot is as long as the tab, a housing as long as the shelf it takes), so built
    designs never match."""
    pk = []
    for p in g.parts:
        for f in p.features:
            if f.op == 'pocket' and f.geom is not None and not f.geom.is_empty and f.geom.geom_type == 'Polygon' \
                    and f.geom.area > MIN_AREA:
                s = _sig(f.geom)
                if s: pk.append(s)
    if not pk:
        return
    for p in g.parts:
        for i in p.inner:
            if i.is_empty or i.area <= MIN_AREA:
                continue
            s = _sig(i)
            if s is None:
                continue
            q = next((q for q in pk if _same(s, q)), None)
            if q:
                yield Finding('GI01', 'error',
                              'through opening %.1f x %.1f mm has the exact size of this file\'s pockets / housings: '
                              'a housing drawn on the through-cut layer is cut out of the part' % (s[0], s[1]), p.key)
                break
