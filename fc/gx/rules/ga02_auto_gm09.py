from shapely import affinity
from shapely.ops import unary_union
from fc.core import Finding
from fc.gx.core import gx_rule

MIN_PART = 5000.0     # mm2: smaller loops are labels / offcuts, not panels with housings
MIN_POCKET = 30.0     # mm2: smaller pocket loops are marks, not housings / rebates
OUTLINE_TOL = 0.01    # outlines match if they differ by <= 1 % of the area
POCKET_TOL = 0.25     # pocket sets match if they differ by <= 25 % of their area (drawing noise, tolerance tweaks)
MAX_PARTS = 400       # guard: files with more pocketed panels than this are not compared pairwise


def _norm(p):
    minx, miny, maxx, maxy = p.outer.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    o = affinity.translate(p.outer, -cx, -cy)
    pf = unary_union([affinity.translate(f.geom, -cx, -cy) for f in p.features
                      if f.op == 'pocket' and f.geom is not None and not f.geom.is_empty])
    return o, pf


def _same(a, b, mirror=False):
    """Is b congruent to a (or to a's mirror image) under a 0/90/180/270 turn, outline AND pockets?"""
    oa, fa = a
    ob, fb = b
    if abs(oa.area - ob.area) > OUTLINE_TOL * oa.area:
        return False
    if mirror:
        ob = affinity.scale(ob, -1.0, 1.0, origin=(0, 0)); fb = affinity.scale(fb, -1.0, 1.0, origin=(0, 0))
    for ang in (0, 90, 180, 270):
        ro = affinity.rotate(ob, ang, origin=(0, 0))
        if ro.symmetric_difference(oa).area > OUTLINE_TOL * oa.area:
            continue
        rf = affinity.rotate(fb, ang, origin=(0, 0))
        if rf.symmetric_difference(fa).area <= POCKET_TOL * max(fa.area, fb.area) + 1.0:
            return True
    return False


@gx_rule('GA02', 'One odd mirror-imaged copy among identical pocketed (handed) parts')
def check(g):
    """Pockets, housings and rebates are cut from the TOP face only, so a panel with pockets is 'handed': its mirror
    image is a different part (left side vs right side). Built furniture uses handed panels in one of two ways:
    all copies the same hand (the parts are turned, not flipped, in assembly - e.g. the pairs of identical sides
    in Opendesk desks and lockers), or matched left/right sets. A shape that appears 3+ times in one hand and
    exactly once in the other is the classic flat-pack drawing error 'one side drawn mirror-imaged': that panel
    gets its housings on the outside face and the shelf / back / hardware cannot be fitted (Opendesk and
    WikiHouse guides: check part orientation and handedness before cutting; cabinet software tracks
    left/right-hand ends for this reason). Panels congruent to their own mirror image are not handed and are
    ignored. Only the odd copy is reported."""
    ps = []
    for p in g.parts:
        o = p.outer
        if o is None or o.is_empty or not o.is_valid or o.area < MIN_PART:
            continue
        if any(f.op == 'pocket' and f.geom is not None and f.geom.area > MIN_POCKET for f in p.features):
            ps.append(p)
    if len(ps) < 4 or len(ps) > MAX_PARTS:
        return
    N = []
    for p in ps:
        try:
            n = _norm(p)
        except Exception:
            n = None
        N.append(n)
    used = set()
    for i in range(len(ps)):
        if i in used or N[i] is None:
            continue
        if _same(N[i], N[i], mirror=True):
            used.add(i); continue        # not handed: mirror image is the same part
        A, B = [i], []
        used.add(i)
        for j in range(i + 1, len(ps)):
            if j in used or N[j] is None:
                continue
            if _same(N[i], N[j]):
                A.append(j); used.add(j)
            elif _same(N[i], N[j], mirror=True):
                B.append(j); used.add(j)
        for one, many in ((A, B), (B, A)):
            if len(one) == 1 and len(many) >= 3:
                yield Finding('GA02', 'error', 'pocketed part is the mirror image of its %d identical twins: pockets '
                              'end up on the wrong face (wrong hand)' % len(many), ps[one[0]].key)
