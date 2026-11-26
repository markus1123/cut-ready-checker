"""GH06: a counterbore (larger round bore / pocket around a hole) not concentric with its hole."""
from fc.core import Finding
from fc.gx.core import gx_rule

OFF_MAX_OK = 0.5    # mm: centre offset that is drawing / export rounding (built designs: <= 0.1 mm)
STEP_MIN = 1.0      # mm: the counterbore radius must exceed the hole radius by this to be a counterbore


@gx_rule('GH06', 'Counterbore off the centre of its hole')
def check(g):
    """A counterbore (the larger, shallower bore that sinks a bolt head, barrel nut or washer) is drilled on the
    same axis as its clearance hole. Drawn off-centre, the head no longer sits in it: it is pushed against one side,
    binds and stands proud, and the counterbore wall half covers the through hole, so the bolt will not line up with
    its nut (Opendesk / AtFAB bolt details; Häfele connector fittings: head bore concentric with the shank bore).
    A round hole whose centre lies inside a larger round bore / pocket in the same part, offset by more than 0.5 mm,
    is flagged; built designs keep these on one centre to within 0.1 mm."""
    for p in g.parts:
        cs = [f for f in p.features if f.r and f.op in ('hole', 'pocket') and f.geom is not None and not f.geom.is_empty]
        if len(cs) < 2 or len(cs) > 2000:
            continue
        done = False
        for b in cs:
            if done: break
            cb = b.geom.centroid
            for a in cs:
                if a is b or b.r < a.r + STEP_MIN:
                    continue
                d = a.geom.centroid.distance(cb)
                if OFF_MAX_OK < d < b.r - 0.5 * a.r:
                    yield Finding('GH06', 'error',
                                  'dia %.1f mm counterbore is %.1f mm off the centre of its dia %.1f mm hole: the head '
                                  'binds on the wall and the bolt does not line up' % (2 * b.r, d, 2 * a.r), p.key)
                    done = True
                    break
