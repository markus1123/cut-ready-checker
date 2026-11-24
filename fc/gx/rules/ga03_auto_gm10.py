import math
from fc.core import Finding
from fc.gx.core import gx_rule

BIT_MIN = 3.175     # mm (1/8"): the smallest router bit that cuts through furniture sheet (Amana 46180)
ROUTER_T = 9.0      # mm: sheet at least this thick is cut on a router, not a laser
MIN_LEN = 3.0       # mm: loops smaller than this are centre marks / export dust, not cut features


def _router_fine(i):
    """A through-cut loop no 1/8" bit fits inside (narrower than the bit everywhere) that is not a round hole
    (round sub-bit holes are G05's business: CAM plunges them)."""
    if i.is_empty or i.geom_type != 'Polygon' or i.area < 1.0:
        return False
    r = i.minimum_rotated_rectangle
    if r.geom_type != 'Polygon':
        return False
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    if max(a, b) < MIN_LEN:
        return False
    if min(a, b) / max(a, b) > 0.9 and i.area > 0.9 * math.pi / 4 * a * b:
        return False
    return i.buffer(-BIT_MIN / 2).is_empty


@gx_rule('GA03', 'Through-cut detail narrower than any router bit in router sheet (text / marks on the cut layer)')
def check(g):
    """Sheet 9 mm and thicker (furniture ply / MDF) is cut on a router, and the smallest bit that cuts through it is
    1/8" = 3.175 mm (docs/rules-from-manuals.md section 5). A through-cut loop that is narrower than that bit
    everywhere - and is not a round hole the CAM can plunge - cannot be routed: typically a part label, number or
    arrow drawn on the profile layer instead of an engrave / mark layer, whose 1-2 mm strokes the bit cannot follow.
    CAM then skips it, cuts a blob, or - with a fine bit - cuts the letters out of a visible face and throws the slugs
    (SendCutSend / Ponoko file prep: text goes on an engrave layer; Vectric: labels are V-carve or engrave
    toolpaths). Thin-sheet files (laser cut, < 9 mm or unknown thickness) are left alone: a laser cuts such detail.
    Sheet thickness comes from the file (layer / manifest / name) or, failing that, from its slot widths."""
    t = g.thickness or g.thickness_est
    if not t or t < ROUTER_T:
        return
    for p in g.parts:
        n = sum(1 for i in p.inner if _router_fine(i))
        if n:
            yield Finding('GA03', 'error', '%d through-cut loop(s) narrower than a 1/8" bit in %.0f mm sheet: text or '
                          'marks on the cut layer?' % (n, t), p.key)
