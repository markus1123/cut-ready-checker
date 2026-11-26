import math
from shapely.geometry import Polygon
from fc.core import Finding
from fc.gx.core import gx_rule

FIN = 1.0        # mm: a protrusion of the outline narrower than this is a fin no cutter leaves standing in plywood
MIN_LEN = 3.0    # mm: shorter is a corner artefact / rounding, not a spur
MIN_W = 0.1      # mm: thinner, the out-and-back lines coincide; the cutter retraces them and no fin is left
MIN_PART = 2500.0
SLIVER = 0.02     # mm
PARALLEL = 0.8    # a spur fills >= 80 % of its bounding rectangle: parallel sides, the out-and-back of a failed join


def spurs(p):
    """Protrusions of the outline narrower than FIN and at least MIN_LEN long: (width, length)."""
    o = Polygon(p.outer.exterior.coords)
    if not o.is_valid or o.area < MIN_PART:
        return []
    op = o.buffer(-FIN / 2, join_style=2, mitre_limit=10).buffer(FIN / 2, join_style=2, mitre_limit=10)
    d = o.difference(op)
    # strip hair-thin slivers the opening shaves off slightly bent straight edges (they would glue onto a spur)
    d = d.buffer(-SLIVER, join_style=2).buffer(SLIVER, join_style=2)
    out = []
    for x in getattr(d, 'geoms', [d]):
        if x.is_empty or x.geom_type != 'Polygon' or x.area < 0.5:
            continue
        r = x.minimum_rotated_rectangle
        if r.geom_type != 'Polygon':
            continue
        c = list(r.exterior.coords)
        w, L = sorted((math.dist(c[0], c[1]), math.dist(c[1], c[2])))
        if MIN_W <= w <= FIN and L >= MIN_LEN and x.area >= PARALLEL * r.area:
            out.append((w, L))
    return out


@gx_rule('GF09', 'Zero-width spur on a part outline (fin narrower than 1 mm)')
def check(g):
    """An outline that runs out to a point and back - a spur left by a failed offset, fillet or join in CAD -
    describes a fin of sheet narrower than 1 mm sticking out of the part edge. The cutter goes round it and leaves
    it standing as a paper-thin wafer of plywood / MDF that splinters off, leaves a ragged edge and stops the edge
    sitting flush against its neighbour (or CAM rejects the self-touching contour). Nothing in furniture is
    designed that thin: the finest end mill made for sheet is 1/16" and built designs have no outline feature under
    1 mm wide. Found by opening the outline with a 1 mm disc: what it removes that is under 1 mm wide, at least
    3 mm long and roughly rectangular is a spur (sharp corners and arc facets are removed as tiny triangles). Spurs under 0.1 mm are coincident lines
    the cutter just retraces - no material is left, so they are harmless.
    Narrowed (misreadings on real files):
      * tapering points (the thin piece fills only 60-70 % of its rectangle: a wedge running from ~1 mm down to
        nothing over 5-25 mm, where two drawn curves meet at a shallow angle - a shelf edge or a decorative leg
        drawn out to a sharp tip): that is a designed sharp point, not a CAD spur. An out-and-back spur from a
        failed offset / join has parallel sides (fills >= 80 %); at a designed point only the last millimetre of
        the tip is too thin to stand, a cosmetic edge, not a fin across the part edge."""
    for p in g.parts:
        s = spurs(p)
        if s:
            w, L = min(s)
            yield Finding('GF09', 'error',
                          'spur %.1f mm wide, %.0f mm long on the part outline: a fin of sheet no cutter can leave '
                          'standing - it splinters off (failed offset / join in CAD?)' % (w, L), p.key)
