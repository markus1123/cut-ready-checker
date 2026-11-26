from fc.gx import limits
from fc.core import Finding
from fc.gx.core import gx_rule

WALL = limits.FINEST   # 1.6 mm (1/16"): less sheet than the finest end mill is wide
TOUCH = 0.2            # mm: closer than this the pocket runs out of the edge (a rebate), which is deliberate
SHALLOW = 3.0          # mm: engraved marks / logos have no wall to load
MIN_POCKET = 50.0      # mm2


@gx_rule('GG07', 'Pocket / housing leaves a wall thinner than any cutter to the part edge')
def check(g):
    """A housing (pocket for a shelf, back panel or fitting) that stops just short of the panel edge leaves a strip
    of sheet between the pocket and the edge that is as tall as the pocket is deep. Under 1.6 mm (the finest 1/16"
    end mill) that wall is torn off by the cutter clearing the pocket, or splits as soon as the part in the housing
    is loaded: the housing ends up open on the edge and the joint loose (Opendesk design guidelines: minimum
    material round pockets; Hettich / Hafele: minimum edge distance for housings and bores). Pockets that run out of
    the edge (rebates, < 0.2 mm) are deliberate, and shallow ones (<= 3 mm: engraved marks) have no wall to load."""
    for p in g.parts:
        o = p.outer
        if o.is_empty or not o.is_valid: continue
        for f in p.features:
            if f.op != 'pocket' or f.geom is None or f.geom.area < MIN_POCKET or not f.geom.is_valid: continue
            if f.depth is not None and f.depth <= SHALLOW: continue
            if g.thickness and f.depth and f.depth >= g.thickness: continue      # cuts through: not a housing
            if not f.geom.within(o.buffer(0.01)): continue
            d = o.exterior.distance(f.geom)
            if TOUCH < d < WALL:
                yield Finding('GG07', 'error', 'pocket on %s is only %.1f mm from the part edge: that wall (thinner '
                              'than any cutter) breaks out and the housing opens on the edge' % (f.layer, d), p.key)
                break
