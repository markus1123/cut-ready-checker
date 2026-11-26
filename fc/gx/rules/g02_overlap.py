from fc.core import Finding
from fc.gx.core import gx_rule
from shapely.strtree import STRtree


MAX_SHARED = 0.2   # mm: thinner overlap = a shared cut line / snapping (common-line nesting), cut once, not a clash
SNAP = 0.5         # mm: ... and up to this on furniture-sized drawings (largest part >= 300 mm across)
SNAP_L = 300.0     # mm
INSIDE = 0.95      # a loop lying this much inside another part's outline is drawn ON that part, not beside it


@gx_rule('G02', 'Parts overlap on the sheet')
def check(g):
    """Two part outlines that overlap (not one inside the other) means cutting one ruins the other. Parts that
    merely share an edge overlap by a hair-thin strip (snap / common-line nesting): that is one cut, not a clash.
    Narrowed after reading real files from other designers:
      * on furniture-sized drawings (largest part >= 300 mm across) overlap strips up to 0.5 mm thick are snapping
        imprecision on a shared edge (parts drawn touching, cut once with a 3+ mm bit; a router's cut tolerance is
        of that order), not one part lying on another;
      * a loop that lies >= 95 % inside another part's outline and pokes past its edge by a sliver is drawn ON that
        part - a cut-out / notch drawn a little past the edge, or the same part stacked twice / a second version
        overlaid - not a second part nested beside it (the reader only treats fully contained loops as openings and
        merges edge notches only into a host 6x bigger). Nesting two parts too close shows as a partial overlap."""
    outs = [p.outer for p in g.parts]
    if len(outs) < 2: return
    L = max(max(o.bounds[2] - o.bounds[0], o.bounds[3] - o.bounds[1]) for o in outs)
    shared = SNAP if L >= SNAP_L else MAX_SHARED
    t = STRtree(outs)
    for i, a in enumerate(outs):
        for j in t.query(a, predicate='intersects'):
            j = int(j)
            if j <= i: continue
            b = outs[j]
            if a.within(b) or b.within(a): continue
            x = a.intersection(b); ov = x.area
            thick = 2 * ov / x.length if x.length else 0     # mean thickness of the overlap strip
            if ov > 1.0 and thick > shared and max(ov / a.area, ov / b.area) < INSIDE:
                yield Finding('G02', 'error', 'parts overlap by %.0f mm2 (%.1f mm deep)' % (ov, thick), g.parts[i].key)
