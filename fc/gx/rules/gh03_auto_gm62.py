"""GH03: a blind pocket or bore that leaves less than 1 mm of sheet under it."""
from fc.core import Finding
from fc.gx.core import gx_rule

FLOOR_MIN = 1.0   # mm. Plywood / MDF sheet thickness varies by +/-0.5 mm (EN 315, APA PS 1; more on cheap ply) and a
                  # spoilboard surfaced to +/-0.2 mm adds to it: a floor under 1 mm breaks through on part of a real
                  # sheet. Built designs in the corpus leave at least 2 mm.


@gx_rule('GH03', 'Blind pocket / bore leaves less than 1 mm of sheet under it')
def check(g):
    """A blind pocket or bore (hinge cup, Minifix housing, rebate, recess) depends on the floor of material left
    under it. Real sheet is +/-0.5 mm off its nominal thickness and the spoilboard is not perfectly flat, so a depth
    that leaves under 1 mm cuts through on part of the sheet or leaves a paper-thin skin that tears out under the
    fitting - the show face is holed and the fitting has nothing to hold on (Blum / Hettich hinge-cup depth 13 mm
    in 16-19 mm board, Häfele Minifix housing depth per board thickness). Only judged when the sheet thickness is
    stated (manifest, file name or the Opendesk through-cut layer) and the feature's depth is on its layer."""
    th = g.thickness
    if not th or not g.thickness_source:
        return
    done = set()
    for p in g.parts:
        if p.key in done:
            continue
        for f in p.features:
            if f.op not in ('pocket', 'hole') or not f.depth or f.depth >= th:
                continue
            floor = th - f.depth
            if floor < FLOOR_MIN:
                done.add(p.key)
                yield Finding('GH03', 'error',
                              '%s %.1f mm deep in %.1f mm sheet leaves a %.2f mm floor: real sheet is +/-0.5 mm, so '
                              'it breaks through or tears out' % (f.op, f.depth, th, floor), p.key)
                break
