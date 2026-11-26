"""GH02: a part outline on the cut-INSIDE layer in a file that puts its part outlines on cut-OUTSIDE layers."""
from fc.core import Finding
from fc.gx.core import gx_rule

MIN_AREA = 20000.0   # mm^2 (e.g. 140 x 140 mm). Smaller free loops on an INSIDE layer are waste slugs / offcuts of
                     # openings in built files, not furniture parts; a real part of this size cut a bit diameter
                     # undersize no longer fits its mates.
MIN_OUTSIDE = 2      # the file must clearly use the convention: at least 2 outlines on an OUTSIDE layer


def _side(layer):
    u = layer.upper()
    if 'OUTSIDE' in u: return 'out'
    if 'INSIDE' in u: return 'in'
    return None


@gx_rule('GH02', 'Part outline on the cut-INSIDE layer (CAM offsets the tool into the part)')
def check(g):
    """Layer-driven CAM (the Opendesk convention TOP-CUT-OUTSIDE_18.000MM / TOP-CUT-INSIDE_18.000MM, and the same
    idea in Vectric / Fusion layer templates) offsets the cutter by its radius to the side the layer names. An
    outline on the INSIDE layer is cut with the bit inside its line, so the part comes out one bit diameter
    (6-9 mm) smaller in each direction: tabs too short, edges miss their slots, the piece will not assemble.
    Judged only when the file clearly follows the convention (>= 2 outlines on OUTSIDE layers), for free-standing
    parts (not nested inside another part's opening, where the same loop is legitimately an INSIDE cut) of at least
    20000 mm^2."""
    if sum(1 for p in g.parts if _side(p.layer) == 'out') < MIN_OUTSIDE:
        return
    for p in g.parts:
        if _side(p.layer) != 'in' or p.outer.area < MIN_AREA:
            continue
        if any(q is not p and q.outer.area > p.outer.area and p.outer.within(q.outer) for q in g.parts):
            continue
        yield Finding('GH02', 'error',
                      'part outline (%.0f x %.0f mm) is on cut-INSIDE layer %s while this file cuts its outlines on '
                      'OUTSIDE layers: CAM offsets the bit into the part and it comes out a bit diameter undersize'
                      % (p.outer.bounds[2] - p.outer.bounds[0], p.outer.bounds[3] - p.outer.bounds[1], p.layer), p.key)
