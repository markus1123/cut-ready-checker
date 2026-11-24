from fc.core import Finding
from fc.gx.core import gx_rule

VENEER = 0.5   # mm: the thinnest floor that still holds together (about one face veneer of birch ply / MDF skin)


def ply_tol(th):
    """Thickness tolerance of sanded plywood, EN 315: +/-(0.2 + 0.03 t) mm (18 mm -> 0.74 mm)."""
    return 0.2 + 0.03 * th


@gx_rule('GC01', 'Pocket so deep it leaves no floor (cuts through the sheet)')
def check(g):
    """A pocket (housing, rebate, hardware recess) is a BLIND cut: it must leave a floor of sheet under it, or the
    router cuts through and what should be a recess becomes a hole - the part is weakened or falls apart, a housed
    shelf has nothing to sit on, a hinge cup / cam housing has no bottom to bear on.
    Sheet goods vary in thickness: EN 315 sanded ply may be 0.2 + 0.03 t mm under nominal (0.74 mm at 18 mm),
    and CAM zeroes depth from the spoilboard or the top face, so a pocket depth closer to the stated sheet
    thickness than that tolerance plus a minimum floor of ~0.5 mm (one face veneer) breaks through on a
    thin sheet. Built designs in the corpus keep at least 2 mm of floor (Opendesk desks: 16 mm pockets in
    18 mm ply). Needs both the stated pocket depth (layer name) and the sheet thickness; otherwise nothing is said."""
    th = g.thickness
    if not th or th < 3:
        return
    lim = th - ply_tol(th) - VENEER
    for p in g.parts:
        worst = None
        for f in p.features:
            if f.op != 'pocket' or not f.depth:
                continue
            if f.depth > lim and (worst is None or f.depth > worst):
                worst = f.depth
        if worst is not None:
            yield Finding('GC01', 'error',
                          'pocket %.1f mm deep in %.1f mm sheet leaves %.1f mm floor (need >= %.1f mm incl. the '
                          'sheet\'s thickness tolerance): the pocket cuts through' % (worst, th, th - worst,
                                                                                      ply_tol(th) + VENEER), p.key)
