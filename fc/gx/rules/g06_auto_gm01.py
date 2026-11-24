from fc.gx import limits
import math
from fc.core import Finding
from fc.gx.core import gx_rule

THIN_STOCK = 0.7    # slots under 0.7 t take deliberately thinner stock: 6-12 mm backs / inlays in a 15-18 mm carcass
BIT_MIN = limits.BIT_MIN     # 1/8": the smallest router bit that cuts through furniture sheet; a narrower through opening is
                    # a saw kerf / kerf-bending cut, not a router-cut slot for a sheet


def ply_tol(th):
    """Lower thickness tolerance of sanded plywood, EN 315: +/-(0.2 + 0.03 t) mm (18 mm -> 0.74 mm)."""
    return 0.2 + 0.03 * th


def _axes(poly):
    r = poly.minimum_rotated_rectangle
    if r.geom_type != 'Polygon':
        return None
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return r, min(a, b), max(a, b)


def _slot_width(i):
    """Width of a rectangular slot-shaped opening (dog-bone / T-bone corner lobes stripped), or None."""
    if i.is_empty or i.geom_type != 'Polygon' or i.area < 50:
        return None
    ax = _axes(i)
    if ax is None or ax[1] <= 0:
        return None
    r, w0, _ = ax
    core = i.buffer(-0.3 * w0).buffer(0.3 * w0)          # morphological opening: removes the small corner lobes
    if core.is_empty or core.geom_type != 'Polygon':
        return None
    ax = _axes(core)
    if ax is None or ax[1] <= 0:
        return None
    r, w, L = ax
    if L < 1.5 * w or core.area < 0.85 * r.area:         # not a straight rectangular slot
        return None
    return w


@gx_rule('G06', 'Slot for a mating sheet narrower than the sheet itself')
def check(g):
    """A slot / mortise that receives another part of the same sheet must be at least as wide as the sheet:
    slot = measured sheet thickness + fit clearance (Opendesk, WikiHouse, ShopBot press-fit guidance). Plywood
    is only ever thinner than nominal by its tolerance, EN 315 sanded ply: 0.2 + 0.03 t mm (0.56 mm at 12 mm,
    0.74 mm at 18 mm). So a slot narrower than nominal by more than that cannot take ANY in-tolerance sheet:
    the tab will not go in, or splits the ply when hammered home. Built designs draw slots at 0.97-1.25 x t.
    Openings under 0.7 t are taken as slots for deliberately thinner stock (backs, inlays) and left alone, as are
    openings narrower than the smallest through-cutting router bit (1/8"), which are kerfs, not slots. Only straight rectangular through openings (dog-bones allowed) whose width is within that band are judged.
    Pockets are not judged: a blind recess of that size is as often a seat for hardware or a locating rebate
    (Opendesk wiki-booth / fin-locker pockets at 0.92 t, built many times) as a housing for the sheet.
    Needs the sheet thickness (manifest / layer depth); without it nothing is said."""
    th = g.thickness
    if not th or th < 3:
        return
    lo, hi = max(THIN_STOCK * th, BIT_MIN), th - ply_tol(th)
    for p in g.parts:
        for i in p.inner:
            w = _slot_width(i)
            if w is not None and lo <= w < hi:
                yield Finding('G06', 'error',
                              'slot %.1f mm wide for %.1f mm sheet: %.1f mm undersize, more than the sheet\'s '
                              'thickness tolerance (%.2f mm) - the mating part will not fit'
                              % (w, th, th - w, ply_tol(th)), p.key)
                break
