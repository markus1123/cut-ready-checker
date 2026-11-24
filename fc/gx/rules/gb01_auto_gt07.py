from fc.core import Finding
from fc.gx.core import gx_rule

MIN_WEB = 2.0      # mm: thinner than this a strip of ply/MDF between an opening and the part edge breaks
BREAKOUT = 1.0     # mm: a strip this thin is a single face veneer: it tears off along the grain as the cut passes,
                   # so the opening becomes an edge notch - some designers draw notches that way on purpose
MIN_OPEN = 200.0   # mm2: smaller openings are drilled holes (G04 judges those)
MIN_PART = 2500.0  # mm2 (~50 x 50 mm): smaller loops are lettering / decoration, not furniture parts


@gx_rule('GB01', 'Opening leaves a web under 2 mm to the part edge')
def check(g):
    """A through-opening (slot, mortise, cut-out, handle hole) needs a strip of material between it and the part's
    outer edge. Plywood face veneers are 0.6-1.5 mm thick and MDF/particle board has no long fibres, so a strip
    under 2 mm is one or two plies wide: it snaps when the second of the two cuts passes (the part is no longer held
    on that side, the cutter deflects into it), chips out on a compression bit's upcut, or breaks the first time the
    joint is loaded. Workshop and CNC design guides put the minimum web at about the bit diameter / sheet
    thickness; 2 mm is far below that. Strips of 1 mm and less are not webs: a single veneer ply tears off as the
    cut passes and the opening simply becomes an edge notch, which is how some designers draw notches (built
    files have openings 0-0.2 mm from the edge)."""
    for p in g.parts:
        if p.outer.area < MIN_PART or not p.outer.is_valid:
            continue
        ext = p.outer.exterior
        for i in p.inner:
            if i.is_empty or i.geom_type != 'Polygon' or i.area < MIN_OPEN or not i.is_valid:
                continue
            if not i.within(p.outer):
                continue
            d = ext.distance(i)
            if BREAKOUT < d < MIN_WEB:
                yield Finding('GB01', 'error', 'opening (%.0f mm2) leaves only %.1f mm of material to the part edge: '
                              'the web breaks while cutting or in use (min %.0f mm)' % (i.area, d, MIN_WEB), p.key)
                break
