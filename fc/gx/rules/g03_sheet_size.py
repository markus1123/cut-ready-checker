from fc.gx import limits
from fc.core import Finding
from fc.gx.core import gx_rule

SHEETS = limits.SHEETS   # largest common furniture sheet formats (incl. 10x5 ft)
FRAME_OPENINGS = 20       # a border around a layout encloses the whole nest: dozens of 'openings' (the parts)
FRAME_HOLDS = 5           # ... and the parts' own holes / lettering show up as parts inside those 'openings'
CM_PER_IN = 2.54          # an inch reading is 2.54x a cm reading of the same unitless numbers


def _fits(L, W):
    return any(L <= a + 0.5 and W <= b + 0.5 for a, b in SHEETS)   # 0.5 mm: CAD rounding


@gx_rule('G03', 'Part does not fit any stock sheet')
def check(g):
    """A part longer/wider than every stock sheet (rotation allowed) cannot be cut in one piece.
    Narrowed (misreadings on real files):
      * drawing frame / sheet border: a plain 4-corner rectangle with 20+ 'openings' and 5+ parts inside them is the border
        drawn around the layout (Kadushin files, nested-plan templates), not a part - its 'openings' are the real parts
        and a part cannot hold other parts; the reader only drops such borders when they match a stock size or hold big parts.
      * unit guess: a file with no unit header that was read as inches only because the mm reading was too small
        (units 'in?') is just as plausibly drawn in cm; when the part fits a sheet at the cm reading, its size at
        the guessed inch scale (2-3 m chair sides, 'tables' bigger than a room) is the guess, not the design."""
    for p in g.parts:
        minx, miny, maxx, maxy = p.outer.bounds
        L, W = max(maxx - minx, maxy - miny), min(maxx - minx, maxy - miny)
        if _fits(L, W):
            continue
        if g.units == 'in?' and _fits(L / CM_PER_IN, W / CM_PER_IN):
            continue
        if len(p.outer.exterior.coords) <= 5 and p.outer.area > 0.99 * (maxx - minx) * (maxy - miny) and \
                len(p.inner) >= FRAME_OPENINGS and sum(1 for q in g.parts if q is not p and
                                                       any(q.outer.within(i) for i in p.inner)) >= FRAME_HOLDS:
            continue
        yield Finding('G03', 'error', 'part %.0f x %.0f mm does not fit a stock sheet' % (L, W), p.key)
