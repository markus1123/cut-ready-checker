"""GJ06: a closed loop inside a housing pocket on the same pocket depth: the CAM leaves it standing as an island."""
from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx import limits

SHALLOW = 3.0        # mm: engraved marks / logos, not housings
MIN_HOUSING = 300.0  # mm2: a housing that takes a part
MIN_ISLAND = limits.BIT_MIN ** 2   # mm2: a loop a bit can go round; smaller loops are centre marks
DEPTH_TOL = 0.1      # mm: same depth layer


@gx_rule('GJ06', 'Closed loop inside a housing pocket at the same depth (left standing as an island)')
def check(g):
    """Pocketing toolpaths treat every closed vector inside a pocket boundary as an island and machine round it
    (Vectric VCarve / Aspire, Fusion 360 2D pocket: inner closed contours become islands). A loop on the same pocket
    depth fully inside a housing - a construction square, a label box, a hardware outline left on the pocket layer -
    leaves a full-height pillar of sheet standing in the housing, so the shelf / back / fitting does not go in.
    A loop inside a pocket at a DIFFERENT depth is a stepped pocket or a bore in its floor (deliberate); a loop on the
    same depth is never wanted: if the area were meant to be pocketed too, it would not be drawn."""
    for p in g.parts:
        pk = [f for f in p.features if f.op == 'pocket' and f.geom is not None and not f.geom.is_empty
              and f.geom.is_valid and f.depth is not None and f.depth > SHALLOW]
        if len(pk) > 500:
            continue
        hit = None
        for a in pk:
            if a.geom.area < MIN_HOUSING:
                continue
            inner = a.geom.buffer(-0.05)
            for b in pk:
                if b is a or b.geom.area < MIN_ISLAND or b.geom.area > 0.5 * a.geom.area:
                    continue
                if abs(b.depth - a.depth) <= DEPTH_TOL and b.geom.within(inner):
                    hit = (a, b); break
            if hit:
                break
        if hit:
            a, b = hit
            yield Finding('GJ06', 'error', '%.0f mm2 loop inside a %.0f mm2 housing on the same %.1f mm pocket depth '
                          '(%s): CAM leaves it as an island of full-height sheet in the housing'
                          % (b.geom.area, a.geom.area, a.depth, a.layer), p.key)
