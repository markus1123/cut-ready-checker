"""GI06: one slot / cut-out of one of two identical parts out of place, all its other openings matching the twin."""
from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx.rules.gg09_auto_gm57 import _poses

MIN_PART = 10000.0   # mm2: panels, not trim
MIN_OPEN = 100.0     # mm2: slots / cut-outs; smaller loops are holes and marks
R_HOLE = 12.0        # mm: round openings up to this radius are drilled holes (GG01 / GF07 territory)
POS = 1.0            # mm: the same opening on the twin, centre for centre
AREA = 0.02          # ... and the same size within 2 %
SHIFT = (3.0, 40.0)  # mm: a displacement in this range is an edit error, not a different feature
MAX_OPEN = 60


def _ops(p):
    hole = {id(f.geom) for f in p.features if f.op == 'hole' and f.r and f.r <= R_HOLE}
    return [i for i in p.inner if i.area > MIN_OPEN and i.is_valid and id(i) not in hole]


@gx_rule('GI06', 'One slot / cut-out of one of two identical parts out of place')
def check(g):
    """Copies of a part (pairs of sides, legs, rails) are machined alike because each slot receives the same mating
    part at the same place (Opendesk / AtFAB slot-together guides). When two parts have the same outline and the
    same set of slots / cut-outs, all of them in the same places but ONE, which has the same shape and size on
    both but sits 3-40 mm away from where the twin has it, that opening was moved by an edit (dragged, snapped to
    the wrong point, nudged): the tab or part that passes through it no longer lines up and the kit cannot be
    assembled square. Twins are matched by outline (rotation and mirroring allowed); a pose in which every
    opening matches clears the pair (symmetric parts)."""
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid]
    if len(parts) > 300: return
    O = {id(p): _ops(p) for p in parts}
    done = set()
    for x, a in enumerate(parts):
        oa = O[id(a)]
        if not oa or len(oa) > MAX_OPEN: continue
        for b in parts[x + 1:]:
            ob = O[id(b)]
            if len(ob) != len(oa) or abs(a.outer.area - b.outer.area) > 0.005 * a.outer.area: continue
            hit, clean = None, False
            for f in _poses(a, b):
                tb = [f(y) for y in ob]
                used, miss = set(), []
                for i in oa:
                    c = i.centroid
                    j = next((n for n, y in enumerate(tb) if n not in used and y.centroid.distance(c) < POS
                              and abs(y.area - i.area) < AREA * i.area), None)
                    if j is None: miss.append(i)
                    else: used.add(j)
                if not miss: clean = True; break
                rest = [tb[n] for n in range(len(tb)) if n not in used]
                if len(miss) == 1 and len(rest) == 1 and abs(rest[0].area - miss[0].area) < AREA * miss[0].area:
                    d = rest[0].centroid.distance(miss[0].centroid)
                    if SHIFT[0] <= d <= SHIFT[1] and hit is None:
                        hit = d
            if clean or hit is None or (a.key, b.key) in done: continue
            done.add((a.key, b.key))
            for k in (a.key, b.key):
                yield Finding('GI06', 'error', 'one slot / cut-out of two identical parts is %.1f mm apart between the '
                              'copies, every other opening matches: one copy\'s opening was moved - its mating part does '
                              'not line up' % hit, k)
