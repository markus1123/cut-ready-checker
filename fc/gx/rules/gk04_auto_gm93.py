import math
from fc.core import Finding
from fc.gx.core import gx_rule
from shapely import affinity

MIN_PART = 5000.0   # mm2: smaller loops are labels / offcuts
OFFSET = (0.3, 2.0) # mm: a copy grown 0.3-2 mm all round is that copy offset by a tool radius / kerf, not a design
                    # change (cutters for sheet are 3-12 mm: radius 1.5-6, a kerf allowance is 0.1-0.5 per side)
FIT = 0.004         # the offset copy must match its twin to 0.4 % of its area (~ the whole outline within ~0.1 mm)


def _poses(a, b):
    """b's outline moved onto a's centroid, rotated 0/90/180/270 and optionally mirrored."""
    ca, cb = a.centroid, b.centroid
    ob = affinity.translate(b, ca.x - cb.x, ca.y - cb.y)
    for mir in (False, True):
        o = affinity.scale(ob, -1, 1, origin=ca) if mir else ob
        for ang in (0, 90, 180, 270):
            yield affinity.rotate(o, ang, origin=ca)


@gx_rule('GK04', 'One of two identical parts drawn offset (fat or thin) all round compared with its twin')
def check(g):
    """Identical parts (pairs of sides, legs, rails) are cut from one drawing. When one part is exactly its twin grown
    by 0.3-2 mm all round, that copy had tool compensation / a kerf offset baked into its geometry (or an offset
    command hit the wrong copy), and CAM offsets it again: that part comes out up to 4 mm too big, its slots and holes
    too small, so its joints do not go together while its twin's do (the mirror case: a copy offset inwards is loose).
    Detected by shrinking the bigger copy by the offset its extra area implies (area / perimeter) and comparing the
    outlines; a part with an exact twin elsewhere in the file is taken as right."""
    if g.scale_uncertain: return       # unitless model-scale drawing: a 1.5 'mm' offset may be 15 mm, not a kerf
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid]
    if len(parts) > 300: return
    ex = set()
    for a in parts:
        for b in parts:
            if a is not b and abs(a.outer.area - b.outer.area) < 0.001 * a.outer.area and \
                    abs(a.outer.length - b.outer.length) < 0.001 * a.outer.length:
                ex.add(id(a)); break
    dims = {}
    for p in parts:
        r = p.outer.minimum_rotated_rectangle
        c = list(r.exterior.coords) if r.geom_type == 'Polygon' else [(0, 0)] * 3
        dims[id(p)] = sorted((math.dist(c[0], c[1]), math.dist(c[1], c[2])))
    hit = {}
    for a in parts:                       # a = the bigger copy
        for b in parts:
            if a is b or a.outer.area <= b.outer.area: continue
            d = (a.outer.area - b.outer.area) / b.outer.length
            if not (OFFSET[0] <= d <= OFFSET[1]): continue
            if abs(dims[id(a)][0] - 2 * d - dims[id(b)][0]) > 0.5 or abs(dims[id(a)][1] - 2 * d - dims[id(b)][1]) > 0.5:
                continue                  # the bounding box must shrink by the same offset too
            s = a.outer.buffer(-d, join_style=2)
            if not s.is_valid: s = s.buffer(0)
            if s.is_empty or s.geom_type != 'Polygon' or not s.is_valid: continue
            if any(o.is_valid and o.symmetric_difference(s).area < FIT * b.outer.area for o in _poses(s, b.outer)):
                hit.setdefault(id(a), (a, d, 'bigger')); hit.setdefault(id(b), (b, d, 'smaller'))
    for k, (p, d, which) in hit.items():
        if k in ex: continue
        yield Finding('GK04', 'error',
                      'this part is an identical part in this file offset %.2f mm all round (%s copy): tool compensation '
                      'or a kerf offset was applied to one copy only - its joints will not fit like its twin\'s'
                      % (d, which), p.key)
