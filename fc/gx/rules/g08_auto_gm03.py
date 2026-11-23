from fc.core import Finding
from fc.gx.core import gx_rule

R_MAX = 12.0     # drilled / fitting bores (dowel, screw pilot, shelf pin, cam housing Ø15-25); bigger rounds are openings
WALL_MIN = 2.0   # mm of solid board that must stay between two neighbouring bores


@gx_rule('G08', 'Two drilled holes so close that the wall between them breaks')
def check(g):
    """Two bores in the same part need a solid wall between them. With under 2 mm of material between the two
    hole edges, the bridge is thinner than a single ply veneer / the crushed zone a drill or plunging bit
    leaves around its hole (MDF and particle board crumble, ply delaminates). It tears out when the second hole is
    drilled (the bit deflects into the first) or as soon as a screw, dowel or cam fitting loads it, and the two
    fittings then share one hole and lose their hold. Fitting makers keep bores far apart for this reason
    (System 32: Ø5 holes on 32 mm pitch; Minifix housing and bolt bores 24-34 mm apart), and the edge-distance
    limit for a single hole (G04, 1.5 mm) is the same physics with only one side drilled. 2 mm is that edge
    limit plus the CNC/drill position tolerance on the second hole. Built designs in the corpus all keep 4 mm or more.
    Concentric bores (counterbores, stepped holes) and a bore lying wholly inside another are one hole, not two."""
    for p in g.parts:
        hs = [f for f in p.features if f.op == 'hole' and f.r and f.r <= R_MAX
              and f.geom is not None and not f.geom.is_empty]
        if len(hs) < 2:
            continue
        worst = None
        for i, a in enumerate(hs):
            ca = a.geom.centroid
            for b in hs[i + 1:]:
                if ca.distance(b.geom.centroid) < 1.0:
                    continue                                   # same bore drawn twice / counterbore
                if a.geom.within(b.geom) or b.geom.within(a.geom):
                    continue                                   # stepped bore
                w = a.geom.distance(b.geom)
                if w < WALL_MIN and (worst is None or w < worst[0]):
                    worst = (w, a, b)
        if worst:
            w, a, b = worst
            yield Finding('G08', 'error',
                          'bores r=%.1f and r=%.1f leave only %.1f mm of material between them (need >= %.1f mm): '
                          'the wall tears out when drilled or loaded' % (a.r, b.r, w, WALL_MIN), p.key)
