import math
from fc.core import Finding
from fc.gx.core import gx_rule
from shapely import affinity

MIN_PART = 5000.0   # mm2: smaller loops are labels / offcuts
DIM_TOL = 1.0       # mm: twins have the same bounding box (a notch bottom moved does not change it)
AREA_TOL = 0.06     # a shortened notch changes the part area by a few %; other parts differ more
SLIVER = 0.25       # mm: differences thinner than this are CAD rounding between copies
SHORT = 0.2         # the notch is at least 20 % shallower than its twin's (CAD rounding is far below that)
KEEP = 0.75         # ... but at least a quarter of it is still there (otherwise the parts are simply different)


def _rect(x):
    r = x.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return None
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return min(a, b), max(a, b), r


def _poses(a, b):
    """b moved onto a's bounding box for each rotation 0/90/180/270, plain and mirrored."""
    ax0, ay0, ax1, ay1 = a.bounds
    for mir in (False, True):
        ob = affinity.scale(b, -1, 1, origin='centroid') if mir else b
        for ang in (0, 90, 180, 270):
            r = affinity.rotate(ob, ang, origin='centroid')
            x0, y0, x1, y1 = r.bounds
            if abs((x1 - x0) - (ax1 - ax0)) > DIM_TOL or abs((y1 - y0) - (ay1 - ay0)) > DIM_TOL: continue
            yield affinity.translate(r, (ax0 + ax1) / 2 - (x0 + x1) / 2, (ay0 + ay1) / 2 - (y0 + y1) / 2)


def _clean(x):
    x = x.buffer(-SLIVER, join_style=2).buffer(SLIVER, join_style=2)
    return [y for y in getattr(x, 'geoms', [x]) if not y.is_empty and y.geom_type == 'Polygon' and y.area > 20]


@gx_rule('GG02', 'Slot-together notch shallower than the same notch on the identical part')
def check(g):
    """Slot-together furniture (cross-halving / egg-crate joints, Opendesk and AtFAB slot joints) holds parts by edge
    notches about one sheet thickness wide, and a notch's depth is set by the joint: the two notches of a halving add
    up to the part height (Digital Wood Joints library, WikiHouse guide - joints must seat fully). Copies of the same
    part (pairs of legs, rails, ribs) carry the same notches. When a part is identical to another one in the file
    except that one sheet-thickness notch (at least 1.5 thicknesses deep on the twin) stops 20-75 % short of where the twin's notch ends, the joint on
    that copy cannot be pushed home: the parts stop proud, the top edges do not line up and the piece rocks.
    Twins are matched by bounding box and outline (rotation and mirroring allowed)."""
    th = g.thickness or g.thickness_est
    if not th: return
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid]
    if len(parts) > 300: return
    outs = [p.outer for p in parts]
    for i, a in enumerate(outs):
        hit = None
        for j, b in enumerate(outs):
            if i == j or abs(a.area - b.area) > AREA_TOL * a.area or b.area > a.area * 0.9995: continue   # the twin has LESS material
            for bb in _poses(a, b):
                extra_b = _clean(bb.difference(a))      # twin has material where this part has none
                if sum(x.area for x in extra_b) > 0.002 * a.area: continue
                extra_a = _clean(a.difference(bb))      # this part has material where the twin has a notch
                if len(extra_a) != 1: continue
                x = extra_a[0]
                rr = _rect(x)
                if rr is None: continue
                w, L, r = rr
                # the extra material fills the notch across its full width: one side ~ sheet thickness
                side = w if 0.9 * th <= w <= 1.5 * th else (L if 0.9 * th <= L <= 1.5 * th else None)
                if side is None or x.area < 0.8 * r.area: continue
                short = x.area / side
                # depth of the twin's notch: the hull pocket of the twin around this region
                hull = bb.buffer(30, join_style=2).buffer(-30, join_style=2).difference(bb)
                pocket = [y for y in getattr(hull, 'geoms', [hull]) if y.intersects(x.buffer(0.5))]
                if not pocket: continue
                depth = max(y.area for y in pocket) / side
                full = depth
                # a real slot-together slot (>= 1.5 sheet thicknesses deep) that is still there on this copy, only
                # shorter; a notch the twin has and this part lacks (or nearly lacks) is a different part, not an error
                if full >= 1.5 * th and SHORT * full <= short <= KEEP * full and short >= 0.5 * th:
                    hit = (short, full); break
            if hit: break
        if hit:
            yield Finding('GG02', 'error',
                          'a %.0f mm wide slot-together notch here is %.0f mm shallower than the same notch on an identical '
                          'part (%.0f mm deep there): the joint cannot seat, the parts stop proud' % (th, hit[0], hit[1]),
                          parts[i].key)
