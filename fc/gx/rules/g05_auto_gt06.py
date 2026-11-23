import math
from fc.core import Finding
from fc.gx.core import gx_rule

BIT_MIN = 3.175     # 1/8" - the smallest router bit that still cuts through furniture sheet (Amana 46180, 20.6 mm flute)
PLUNGE_SLACK = 0.4  # how much a plunged hole may come out oversize and still work as a screw pilot / locator
D_MIN = BIT_MIN - PLUNGE_SLACK   # 2.775 mm


@gx_rule('G05', 'Round through-cut hole smaller than the smallest router bit')
def check(g):
    """A round through opening on a router cut layer is made by the router bit itself. The smallest bit that can
    still cut through furniture sheet is 1/8" = 3.175 mm (docs/rules-from-manuals.md section 5; thinner bits
    have flutes far shorter than a sheet is thick and snap). CAM software turns a circle smaller than the bit
    into a plunge, so the hole comes out at 3.175 mm. Drawn holes a little under that (AtFAB's 2.8-3.0 mm
    pilot holes, built many times) still work: a screw pilot or locator takes ~0.4 mm oversize. Below
    3.175 - 0.4 = 2.775 mm the drawn size is a drill-only size: the router can't make it, the plunged hole
    is >15% too big for what it was drawn for, and with a thinner bit the bit breaks.
    Only true circles are judged (area >= 90% of the circle on the bounding box): small non-round loops are
    lettering or marks, cut part-way with a V-bit. Holes on drill layers are left to a drilling unit."""
    for p in g.parts:
        for i in p.inner:
            if i.is_empty or i.geom_type != 'Polygon' or not i.within(p.outer.buffer(0.01)):
                continue
            mr = i.minimum_rotated_rectangle
            if mr.geom_type != 'Polygon':
                continue
            xs = list(mr.exterior.coords)
            a, b = math.dist(xs[0], xs[1]), math.dist(xs[1], xs[2])
            short, long_ = min(a, b), max(a, b)
            if long_ <= 0 or short / long_ < 0.9 or i.area < 0.9 * math.pi / 4 * short * long_:
                continue
            d = 2 * math.sqrt(i.area / math.pi)        # equivalent-area diameter
            if d < D_MIN:
                yield Finding('G05', 'error',
                              'round through hole %.1f mm across: no router bit that size cuts through sheet '
                              '(smallest is 1/8" = %.2f mm)' % (d, BIT_MIN), p.key)
