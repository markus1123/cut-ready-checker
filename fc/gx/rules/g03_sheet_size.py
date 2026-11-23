from fc.core import Finding
from fc.gx.core import gx_rule

SHEETS = [(2500, 1250), (3050, 1525)]   # largest common furniture sheet formats (incl. 10x5 ft)


@gx_rule('G03', 'Part does not fit any stock sheet')
def check(g):
    """A part longer/wider than every stock sheet (rotation allowed) cannot be cut in one piece."""
    for p in g.parts:
        minx, miny, maxx, maxy = p.outer.minimum_rotated_rectangle.bounds if False else p.outer.bounds
        L, W = max(maxx - minx, maxy - miny), min(maxx - minx, maxy - miny)
        if not any(L <= a and W <= b for a, b in SHEETS):
            yield Finding('G03', 'error', 'part %.0f x %.0f mm does not fit a stock sheet' % (L, W), p.key)
