"""GH09: a drilled hole that straddles the part outline (its bore breaks out of the edge)."""
from fc.core import Finding
from fc.gx.core import gx_rule

R_MAX = 12.0     # drilled bores (screws, dowels, pins, bolts); larger circles are cut-outs / finger pulls
CUT_MIN = 0.3    # mm the bore must reach past the edge: less is drawing tolerance (bore tangent to the edge)


@gx_rule('GH09', 'Drilled hole straddles the part edge')
def check(g):
    """A screw, dowel, pin or bolt bore whose centre is inside the part but whose circle crosses the outline is cut
    open along the edge: the fixing gets a groove instead of a hole and nothing to grip, the drill catches the edge
    and splinters the veneer, and the edge gets a bite where its mate should sit flush (Häfele / Hettich drilling
    guides: minimum edge distance for every bore; Opendesk: hardware holes fully inside the part). Typical causes:
    the circle snapped to the edge line, or the outline trimmed / offset after the holes were placed. Built designs
    have no bore crossing their outline."""
    for p in g.parts:
        ext = p.outer.exterior
        for f in p.features:
            if f.op != 'hole' or not f.r or f.r > R_MAX or f.geom is None or f.geom.is_empty:
                continue
            c = f.geom.centroid
            if not p.outer.contains(c):
                continue
            out = f.r - ext.distance(c)
            if out > CUT_MIN:
                yield Finding('GH09', 'error',
                              'dia %.1f mm bore crosses the part edge by %.1f mm: it is cut open along the edge and '
                              'the fixing has nothing to grip' % (2 * f.r, out), p.key)
                break
