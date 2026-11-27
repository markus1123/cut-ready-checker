"""GI07: dog-bone corner reliefs far smaller than any bit that cuts through the sheet."""
import math
import shapely
from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx import limits

MIN_W = 6.0       # mm: openings narrower than this have no room for dog-bones anyway
LOBE_MIN = 0.5    # mm2: smaller bits of difference are flattening noise, not drawn lobes
CORNER = 2.5      # mm: a lobe within this of a core corner is a corner relief


def _axes(poly):
    r = poly.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return None
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return r, min(a, b), max(a, b)


@gx_rule('GI07', 'Dog-bones drawn far smaller than any bit that cuts through the sheet')
def check(g):
    """Dog-bone / T-bone reliefs exist so the round cutting bit can reach into a square inside corner: each relief
    must be at least the bit's diameter (ShopBot / Fab Academy dog-bone guidance; Fusion 360 and Inkscape dog-bone
    add-ons take the tool diameter as input). No bit under 1/8" (3.175 mm) cuts through furniture sheet. When a
    rectangular opening has corner reliefs at 3+ of its corners and every one of them fits in a circle of radius
    under half that (they were drawn for a ~2 mm tool), CAM cannot enter them: the corners stay rounded at the
    real bit's radius and the square-edged mating part does not seat - the reliefs do nothing."""
    rmax = limits.BIT_MIN / 2 * 0.8   # part of a relief outside the corner: < 1.27 mm radius = drawn for a ~2 mm tool
    for p in g.parts:
        if len(p.inner) > 400: continue
        for i in p.inner:
            if i.area < 50 or not i.is_valid: continue
            ax = _axes(i)
            if ax is None or ax[1] < MIN_W: continue
            rad = min(6.0, 0.3 * ax[1])
            core = i.buffer(-rad).buffer(rad)
            if core.is_empty or core.geom_type != 'Polygon': continue
            cax = _axes(core)
            if cax is None or core.area < 0.85 * cax[0].area or core.area < 0.8 * i.area: continue
            rect = cax[0]
            if not rect.buffer(-0.3).within(i): continue
            d = i.difference(rect.buffer(0.05, join_style=2))
            lobes = [x for x in getattr(d, 'geoms', [d]) if not x.is_empty and x.area > LOBE_MIN]
            if len(lobes) < 3: continue
            corners = [shapely.Point(c) for c in list(rect.exterior.coords)[:4]]
            if not all(min(x.distance(c) for c in corners) < CORNER for x in lobes): continue
            if all(shapely.minimum_bounding_radius(x) < rmax for x in lobes):
                yield Finding('GI07', 'error', 'dog-bones of this %.1f mm opening are only ~%.1f mm across: no bit that '
                              'cuts through the sheet (>= %.2f mm) fits into them, the corners stay rounded'
                              % (ax[1], 2 * max(shapely.minimum_bounding_radius(x) for x in lobes), limits.BIT_MIN), p.key)
                break
