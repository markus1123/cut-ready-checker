from fc.core import Finding
from fc.gx.core import gx_rule

MIN_POCKET = 150.0   # mm2: a housing, not a mark
MIN_OPEN = 200.0     # mm2: a slot / cut-out
SHALLOW = 3.0        # mm: engraved marks have no floor or wall to lose
CORNER = 0.05       # a pocket under 5 % of the opening's area at its edge is a corner / end relief
LO, HI = 0.15, 0.85  # share of the housing lying over the opening: a real crossing, not a touch or a full overlap


@gx_rule('GG10', 'Housing (pocket) runs partly into a through slot / cut-out')
def check(g):
    """A housing carries its shelf / back / fitting on its floor and side walls. Where a housing partly overlaps a
    through opening of the same part it has neither there: the part it should hold drops into the opening, the
    sliver of sheet between the two cuts breaks out, and the slot loses the edge its mating part bears on (Opendesk
    design guidelines: keep material between pockets and through cuts). Counterbores / recesses that wholly contain
    an opening (a pocket round a hole or slot), pockets wholly inside an opening, pockets exactly as wide as the
    slot they continue (stepped slots, Opendesk Lift desk) and small corner reliefs (< 5 % of the opening, Opendesk
    Lean Collaboration table) are deliberate and not flagged, nor are shallow (<= 3 mm) engraved marks."""
    for p in g.parts:
        ops = [i for i in p.inner if i.area > MIN_OPEN and i.is_valid]
        if not ops: continue
        for f in p.features:
            x = f.geom
            if f.op != 'pocket' or x is None or x.area < MIN_POCKET or not x.is_valid: continue
            if f.depth is not None and f.depth <= SHALLOW: continue
            bad = None
            for o in ops:
                if not o.intersects(x) or o.within(x.buffer(0.5)) or x.within(o.buffer(0.5)): continue
                if x.area < CORNER * o.area: continue          # small corner / end relief of a big opening
                (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = x.bounds, o.bounds
                if (abs(ax0 - bx0) < 0.5 and abs(ax1 - bx1) < 0.5) or (abs(ay0 - by0) < 0.5 and abs(ay1 - by1) < 0.5):
                    continue                                   # same width as the slot: a stepped slot, deliberate
                share = o.intersection(x).area / x.area
                if LO <= share <= HI:
                    bad = share; break
            if bad is not None:
                yield Finding('GG10', 'error', 'pocket on %s lies %.0f%% over a through slot / cut-out: the housing has '
                              'no floor or wall there and the sheet between them breaks out' % (f.layer, 100 * bad), p.key)
                break
