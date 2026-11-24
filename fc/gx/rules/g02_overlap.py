from fc.core import Finding
from fc.gx.core import gx_rule
from shapely.strtree import STRtree


MAX_SHARED = 0.2   # mm: thinner overlap = a shared cut line / snapping (common-line nesting), cut once, not a clash


@gx_rule('G02', 'Parts overlap on the sheet')
def check(g):
    """Two part outlines that overlap (not one inside the other) means cutting one ruins the other. Parts that
    merely share an edge overlap by a hair-thin strip (snap / common-line nesting): that is one cut, not a clash."""
    outs = [p.outer for p in g.parts]
    if len(outs) < 2: return
    t = STRtree(outs)
    for i, a in enumerate(outs):
        for j in t.query(a, predicate='intersects'):
            j = int(j)
            if j <= i: continue
            b = outs[j]
            if a.within(b) or b.within(a): continue
            x = a.intersection(b); ov = x.area
            thick = 2 * ov / x.length if x.length else 0     # mean thickness of the overlap strip
            if ov > 1.0 and thick > MAX_SHARED:
                yield Finding('G02', 'error', 'parts overlap by %.0f mm2 (%.1f mm deep)' % (ov, thick), g.parts[i].key)
