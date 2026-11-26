from fc.core import Finding
import math
from fc.gx.core import gx_rule

MIN_PART = 2500.0   # mm2: smaller loops are lettering / marks, not parts
MIN_INSIDE = 20.0   # mm of the line inside the part: more than a lead-in touching the outline or snapping noise
STRAIGHT = 0.98     # end-to-end distance / length: a construction / centre / reference line is one straight line


@gx_rule('GC04', 'Stray open line on a cut layer runs across a part')
def check(g):
    """Every vector on a through-cut layer is machined through the full sheet. An open line on such a layer that
    enters a part through its outline and leaves it again (crossing it at two or more points, 20+ mm of it inside)
    is cut straight across the part: the part is split in two or left with a full-depth kerf across it. Such lines
    are construction / centre / reference lines that were left on the cut layer (SendCutSend: remove construction
    lines; Opendesk: only toolpath geometry on CUT layers). Lead-ins touch the outline from outside only, and lines
    lying wholly inside a part (marking / folding lines some built Fab Academy files carry) do not split it, so
    neither is flagged.
    Narrowed after reading real files from other designers:
      * only straight lines are construction / centre / reference lines. Curved or wavy open lines crossing a part
        are something else drawn on a single-layer file: the neighbouring slice's profile drawn on each slice of a
        stacked 'layer chair' for glue-up registration, decorative engraving curves, bending lines - the operator
        assigns those an engrave / mark toolpath; they are not a forgotten construction line."""
    for line, layer in g.open_chains:
        if line.length < MIN_INSIDE:
            continue
        if math.dist(line.coords[0], line.coords[-1]) < STRAIGHT * line.length:
            continue
        for p in g.parts:
            o = p.outer
            if o.is_empty or o.area < MIN_PART or not line.intersects(o) or not line.crosses(o):
                continue
            inside = line.intersection(o).length
            pts = line.intersection(o.exterior)
            n = 0 if pts.is_empty else len(getattr(pts, 'geoms', [pts]))
            if n >= 2 and inside > MIN_INSIDE:
                yield Finding('GC04', 'error',
                              'open line on cut layer %s runs %.0f mm across this part, edge to edge: it is cut through '
                              'and splits the part (construction line left on the cut layer?)' % (layer, inside), p.key)
