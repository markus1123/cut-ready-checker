from fc.core import Finding
from fc.gx.core import gx_rule

MARGIN = 3.0      # mm: built designs keep >= 8.7 mm; under 3 mm the cutter (3-12 mm) runs into the sheet's own edge
MIN_PART = 2000.0  # mm2: smaller loops are labels / offcuts
FRAME_SIDES = 2   # parts within MARGIN of this many sides of the border: a frame drawn round the nest, not the stock


def tight_sides(s, parts):
    """How many of the border's 4 sides have a part within MARGIN of them."""
    x0, y0, x1, y1 = s.bounds
    n = 0
    for k in range(4):
        d = min(((b[0] - x0), (b[1] - y0), (x1 - b[2]), (y1 - b[3]))[k] for b in (p.outer.bounds for p in parts))
        n += d < MARGIN
    return n


@gx_rule('GC07', 'Part nested against the edge of the drawn stock sheet (no margin)')
def check(g):
    """Factory sheet edges are not square or straight to the millimetre, are often dented in handling, and are where
    the sheet is screwed / clamped down. A part whose outline comes within 3 mm of the drawn sheet edge has its
    profile toolpath (a cutter of 3-12 mm running half a bit outside the part) partly off the material or into the
    hold-down: the part gets a short, chipped or wandering edge (ShopBot hold-down guide; Vectric nesting 'border
    gap'; Opendesk making guide). Built designs that draw their sheet keep 8.7 mm or more. Only parts wholly on the
    sheet are judged; parts across the border are G12's job.
    Narrowed (misreadings on real files):
      * parts within 3 mm of two or more sides of the border (0-2.5 mm on 2-3 sides in free-site files: a 900 x 600
        laser-bed layout, a 762 x 1194 'sheet' exactly as long as the parts, an oven-rack nest packed into a
        corner): that rectangle is a frame the designer drew round the packed nest (or the bed of a laser, whose
        0.2 mm beam needs no margin and no hold-down screws), not the outline of the stock the router cuts from -
        the operator places that nest on a bigger sheet. A single part pushed against one side of an otherwise
        spaced nest is still flagged."""
    s = g.sheet
    if s is None or s.is_empty:
        return
    on = [p for p in g.parts if not p.outer.is_empty and p.outer.area >= MIN_PART and p.outer.within(s)]
    if not on or tight_sides(s, on) >= FRAME_SIDES:
        return
    for p in on:
        d = s.exterior.distance(p.outer)
        if d < MARGIN:
            yield Finding('GC07', 'error', 'part is only %.1f mm from the edge of the stock sheet (need >= %.0f mm for '
                          'the cutter and the sheet\'s rough edge / hold-down)' % (d, MARGIN), p.key)
