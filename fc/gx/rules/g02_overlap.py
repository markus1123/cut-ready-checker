from fc.core import Finding
from fc.gx.core import gx_rule
from shapely.strtree import STRtree


@gx_rule('G02', 'Parts overlap on the sheet')
def check(g):
    """Two part outlines that overlap (not one inside the other) means cutting one ruins the other."""
    outs = [p.outer for p in g.parts]
    if len(outs) < 2: return
    t = STRtree(outs)
    for i, a in enumerate(outs):
        for j in t.query(a, predicate='intersects'):
            j = int(j)
            if j <= i: continue
            b = outs[j]
            if a.within(b) or b.within(a): continue
            ov = a.intersection(b).area
            if ov > 1.0:
                yield Finding('G02', 'error', 'parts overlap by %.0f mm2' % ov, g.parts[i].key)
