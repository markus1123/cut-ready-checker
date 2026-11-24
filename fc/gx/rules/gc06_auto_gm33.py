import math
from fc.core import Finding
from fc.gx.core import gx_rule

BIT_MIN = 3.175           # 1/8": the smallest router bit that cuts through furniture sheet (Amana 46180)
D_MIN = BIT_MIN - 0.4     # 2.775 mm: what a 1/8" bit can still stand in for (same slack as G05's plunged holes)
MIN_LEN = 8.0             # mm: a slit shorter than this is a sharp corner / drawing noise, not a drawn cut
MAX_SLITS = 2             # a part with a whole row of slits is a kerf-bending / laser pattern made for another tool
MIN_PART = 2500.0         # mm2: smaller loops are lettering / marks


@gx_rule('GC06', 'Slit into a part edge narrower than the smallest router bit')
def check(g):
    """A router cuts with a round bit: no gap in a part outline can be narrower than the bit that cuts it. The
    smallest bit that still cuts through furniture sheet is 1/8" = 3.175 mm (thinner ones have flutes far shorter
    than the sheet is thick and snap). A slit into the part edge (notch, relief or kerf line drawn for a saw blade)
    narrower than 2.775 mm (1/8" less the 0.4 mm a press-fit or relief tolerates) and at least 8 mm long cannot be
    cut as drawn: CAM skips it (VCarve: tool too large for the vector) so the relief is missing, or a bigger bit
    makes it oversize. Found as the parts of the outline's 'closing' with a 2.775 mm disc that lie outside the part.
    Built designs in the corpus have no such slits (narrowest drawn edge slit 2.8 mm). Parts with more than two
    are kerf-bending / laser patterns meant for another tool and are left alone."""
    for p in g.parts:
        o = p.outer
        if o.is_empty or not o.is_valid or o.area < MIN_PART:
            continue
        c = o.buffer(D_MIN / 2, join_style=2).buffer(-D_MIN / 2, join_style=2)
        d = c.difference(o)
        slits = []
        for x in getattr(d, 'geoms', [d]):
            if x.is_empty or x.geom_type != 'Polygon' or x.area < 10:
                continue
            r = x.minimum_rotated_rectangle
            if r.geom_type != 'Polygon':
                continue
            cs = list(r.exterior.coords)
            a, b = math.dist(cs[0], cs[1]), math.dist(cs[1], cs[2])
            if max(a, b) >= MIN_LEN and x.area >= 0.6 * r.area:
                slits.append((min(a, b), max(a, b)))
        if 1 <= len(slits) <= MAX_SLITS:
            w, L = min(slits)
            yield Finding('GC06', 'error',
                          'slit %.1f mm wide, %.0f mm deep in the part edge: narrower than the smallest through-cutting '
                          'router bit (1/8" = %.2f mm) - it cannot be cut as drawn' % (w, L, BIT_MIN), p.key)
