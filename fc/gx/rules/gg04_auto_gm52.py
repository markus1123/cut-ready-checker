from fc.core import Finding
from fc.gx.core import gx_rule

R_MAX = 12.0        # mm: drilled / fitting holes; bigger round openings are cut-outs
R_MIN = 1.5         # mm: smaller circles are centre marks
MIN_OPEN = 100.0    # mm2: an opening big enough to be a slot / cut-out
BITE = 0.15         # the bore runs at least 15 % of its radius into the opening (more than CAD snapping)


@gx_rule('GG04', 'Drilled hole breaks into a slot / cut-out of the same part')
def check(g):
    """A bore for a screw, dowel, cam or pin needs a full wall of sheet all round it: Hafele / Hettich fitting
    instructions place bores in solid material, clear of panel edges and other machining. A hole whose centre is in
    solid sheet but whose rim runs into a slot or cut-out of the same part has no wall on that side: the drill
    wanders into the gap and tears out the slot edge, and the fitting has nothing to grip on that side and pulls out.
    Corner reliefs (dog-bone / drilled relief circles centred on or inside an opening's corner) have their centre in
    the opening, not in the sheet, and are not flagged; a rim that only grazes the opening (CAD snapping) is
    ignored."""
    for p in g.parts:
        ops = [i for i in p.inner if i.area > MIN_OPEN and i.is_valid]
        if not ops: continue
        for f in p.features:
            if f.op != 'hole' or not f.r or not (R_MIN <= f.r <= R_MAX) or f.geom is None: continue
            c = f.geom.centroid
            for o in ops:
                if o is f.geom or o.equals(f.geom): continue
                if o.contains(c) or o.exterior.distance(c) < 0.05: continue     # centre in the opening: a relief
                d = o.exterior.distance(c)
                if d < f.r * (1 - BITE):
                    yield Finding('GG04', 'error',
                                  'Ø%.1f hole centred %.1f mm from a slot / cut-out: its rim runs %.1f mm into the '
                                  'opening - no wall on that side, the bore tears out and the fitting will not hold'
                                  % (2 * f.r, d, f.r - d), p.key)
                    break
            else:
                continue
            break
