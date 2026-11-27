from fc.gx import limits
from fc.core import Finding
from fc.gx.core import gx_rule

MIN_GAP = limits.BIT_MIN  # mm: 1/8" - the smallest bit that cuts through furniture sheet; the gap between a cut-out's
                          # edge and a part nested in it must take at least one bit diameter
TOUCH = 0.3               # mm: closer than this the outlines share one cut line (common-line nesting)
MIN_PART = 1500.0         # mm2: smaller loops inside an opening are lettering / logos / slugs, not nested parts
MIN_ROUTER_SLOT = 3.0     # mm: a through-opening narrower than this cannot be routed at all: a laser / waterjet file


def _laser(g):
    for p in g.parts:
        for o in p.inner:
            if o.area > 1.0 and o.is_valid and o.buffer(-MIN_ROUTER_SLOT / 2.0).is_empty:
                return True
    return False


@gx_rule('GK06', 'A part nested inside another part\'s cut-out closer to its edge than a router bit is wide')
def check(g):
    """Part-in-part nesting puts small parts in the waste of a big cut-out (a seat opening, a hand hole). The cut-out
    is cut on a toolpath half a bit inside its line, the small part on one half a bit outside its own: the sheet left
    between the two lines must be at least one bit diameter, or the bit cutting the cut-out also cuts away the edge of
    the nested part (or the two cuts merge and the part sits loose, unheld, and is thrown). The smallest bit that cuts
    through furniture sheet is 1/8" (3.175 mm); CAM nesting sets the part gap >= tool diameter (Vectric part gap,
    Fusion nesting). Outlines that touch (< 0.3 mm, common-line cut) and laser / waterjet files (openings narrower
    than any router bit) are not judged."""
    if g.scale_uncertain: return
    parts = [p for p in g.parts if p.outer.is_valid and not p.outer.is_empty]
    big = [(p, o) for p in parts for o in p.inner if o.is_valid and o.area > 4 * MIN_PART]
    if not big: return
    small = [q for q in parts if q.outer.area >= MIN_PART]
    hits = []
    for p, o in big:
        for q in small:
            if q is p or q.outer.area >= o.area: continue
            if not q.outer.within(o): continue
            d = o.exterior.distance(q.outer)
            if TOUCH < d < MIN_GAP:
                hits.append((q, d))
    if not hits or _laser(g): return
    for q, d in hits:
        yield Finding('GK06', 'error',
                      'this part is nested inside a cut-out only %.1f mm from its edge (needs >= %.1f mm, one bit '
                      'diameter): the bit cutting the cut-out cuts into this part' % (d, MIN_GAP), q.key)
