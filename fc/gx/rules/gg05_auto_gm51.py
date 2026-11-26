import math
from fc.core import Finding
from fc.gx.core import gx_rule

MIN_PART = 5000.0   # mm2: smaller loops are labels / small parts themselves
MIN_TH = 9.0        # mm: thinner sheet (6 mm drawer bottoms, laser ply) carries fine features made for it
W_MAX = 6.0         # mm: a finger narrower than this (and well under the sheet thickness) has no strength
ASPECT = 3.0        # the finger is at least 3x as long as it is wide (a short bump is a chamfer / rounding)
MAX_FINGERS = 2     # a comb of many narrow fingers is a deliberate kerf / laser pattern, left alone


@gx_rule('GG05', 'Narrow finger / tab sticking out of a part edge')
def check(g):
    """A strip of ply or MDF that is much narrower than the sheet is thick has almost no cross-grain strength (half
    its veneers run across it). A finger / tab under 6 mm wide and under 60 % of the sheet thickness, at least 3x as
    long as it is wide, breaks off while the part is cut (the cutter deflects it, the vacuum cannot hold it) or the
    first time the part is handled or assembled (Opendesk design guidelines: tabs and features about a sheet
    thickness wide; Fab Academy CNC week: thin features snap off). Found as what an opening with a 6 mm disc
    removes from the outline. Thin sheet (< 9 mm) and parts with a comb of such fingers (kerf / laser patterns)
    are left alone."""
    th = g.thickness or g.thickness_est
    if not th or th < MIN_TH: return
    wmax = min(W_MAX, 0.6 * th)
    for p in g.parts:
        o = p.outer
        if o.is_empty or not o.is_valid or o.area < MIN_PART: continue
        op = o.buffer(-wmax / 2, join_style=2).buffer(wmax / 2, join_style=2)
        if op.is_empty: continue
        d = o.difference(op.buffer(0.05, join_style=2))
        fingers = []
        for x in getattr(d, 'geoms', [d]):
            if x.is_empty or x.geom_type != 'Polygon' or x.area < 20: continue
            r = x.minimum_rotated_rectangle
            if r.geom_type != 'Polygon': continue
            cs = list(r.exterior.coords)
            a, b = math.dist(cs[0], cs[1]), math.dist(cs[1], cs[2])
            w, L = min(a, b), max(a, b)
            if w <= wmax + 0.1 and L >= ASPECT * w and L >= 12 and x.area >= 0.7 * r.area:
                fingers.append((w, L))
        if 1 <= len(fingers) <= MAX_FINGERS:
            w, L = max(fingers, key=lambda t: t[1])
            yield Finding('GG05', 'error', 'finger %.1f mm wide sticks %.0f mm out of the part edge in %.0f mm sheet: '
                          'too narrow to survive cutting or handling - it breaks off' % (w, L, th), p.key)
