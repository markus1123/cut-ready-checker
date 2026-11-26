from fc.core import Finding
from fc.gx.core import gx_rule
from shapely.strtree import STRtree


MAX_SHARED = 0.2   # mm: thinner overlap = a shared cut line / snapping (common-line nesting), cut once, not a clash
SNAP = 0.5         # mm: ... and up to this on furniture-sized drawings (largest part >= 300 mm across)
SNAP_L = 300.0     # mm
INSIDE = 0.95      # a loop lying this much inside another part's outline is drawn ON that part, not beside it
VIEW = 10          # this many overlapping pairs in one file = an assembly / elevation view, not a nesting slip
BIT_AREA = 7.9     # mm2: footprint of a 1/8" (3.175 mm) bit, the smallest that cuts furniture sheet
MIN_PART = 2500.0  # mm2: loops smaller than this are lettering / marks / logos, not furniture parts (as GB01, G10, GC08)


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
        merges edge notches only into a host 6x bigger). Nesting two parts too close shows as a partial overlap.
      * a file in which 10 or more pairs of parts overlap is drawn as an assembly / elevation view (legs, rails and
        slats shown in place, crossing each other - common in files from free-file sites): the overlaps are how the
        view is drawn. A part nested onto the same material by mistake overlaps only its few neighbours.
      * an overlap smaller than the footprint of the smallest bit (1/8": 7.9 mm2) - two corners or edges drawn
        touching with a little snap error - vanishes inside the kerf that separates the parts anyway; it is not
        one part lying on another. On drawings under 300 mm the allowance shrinks with the drawing's size squared
        (snap / export error is relative to the drawing, and a small drawing may be a scaled model);
      * on furniture-sized drawings, two loops that are BOTH under 2500 mm2 (dots, lettering, logo pieces, tabs of
        a laser model drawn assembled) are not furniture parts nested on the sheet; a real nesting slip involves a
        part."""
    outs = [p.outer for p in g.parts]
    if len(outs) < 2: return
    L = max(max(o.bounds[2] - o.bounds[0], o.bounds[3] - o.bounds[1]) for o in outs)
    shared = SNAP if L >= SNAP_L else MAX_SHARED
    t = STRtree(outs)
    hits = []
    for i, a in enumerate(outs):
        for j in t.query(a, predicate='intersects'):
            j = int(j)
            if j <= i: continue
            b = outs[j]
            if a.within(b) or b.within(a): continue
            x = a.intersection(b); ov = x.area
            thick = 2 * ov / x.length if x.length else 0     # mean thickness of the overlap strip
            if L >= SNAP_L and max(a.area, b.area) < MIN_PART: continue
            if ov > max(1.0, BIT_AREA * min(1.0, L / SNAP_L) ** 2) and thick > shared and max(ov / a.area, ov / b.area) < INSIDE:
                hits.append(Finding('G02', 'error', 'parts overlap by %.0f mm2 (%.1f mm deep)' % (ov, thick), g.parts[i].key))
    if len(hits) < VIEW:
        yield from hits
