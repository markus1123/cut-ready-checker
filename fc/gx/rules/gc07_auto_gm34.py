from fc.core import Finding
from fc.gx.core import gx_rule

MARGIN = 3.0      # mm: built designs keep >= 8.7 mm; under 3 mm the cutter (3-12 mm) runs into the sheet's own edge
MIN_PART = 2000.0  # mm2: smaller loops are labels / offcuts


@gx_rule('GC07', 'Part nested against the edge of the drawn stock sheet (no margin)')
def check(g):
    """Factory sheet edges are not square or straight to the millimetre, are often dented in handling, and are where
    the sheet is screwed / clamped down. A part whose outline comes within 3 mm of the drawn sheet edge has its
    profile toolpath (a cutter of 3-12 mm running half a bit outside the part) partly off the material or into the
    hold-down: the part gets a short, chipped or wandering edge (ShopBot hold-down guide; Vectric nesting 'border
    gap'; Opendesk making guide). Built designs that draw their sheet keep 8.7 mm or more. Only parts wholly on the
    sheet are judged; parts across the border are G12's job."""
    s = g.sheet
    if s is None or s.is_empty:
        return
    for p in g.parts:
        o = p.outer
        if o.is_empty or o.area < MIN_PART or not o.within(s):
            continue
        d = s.exterior.distance(o)
        if d < MARGIN:
            yield Finding('GC07', 'error', 'part is only %.1f mm from the edge of the stock sheet (need >= %.0f mm for '
                          'the cutter and the sheet\'s rough edge / hold-down)' % (d, MARGIN), p.key)
