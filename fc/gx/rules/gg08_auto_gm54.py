import math
from fc.core import Finding
from fc.gx.core import gx_rule
from shapely import affinity

MIN_PART = 5000.0   # mm2
SHAPE_TOL = 0.005   # outlines differing by < 0.5 % of the area are copies of one part
POS_TOL = 1.0       # mm: the same slot on the twin, centre for centre
SHORT = 0.8         # this mortise has under 80 % of the twin's mortise length


def _ax(x):
    r = x.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return None
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return min(a, b), max(a, b), r


def _poses(a, b):
    ca, cb = a.outer.centroid, b.outer.centroid
    for mir in (False, True):
        ob = affinity.translate(b.outer, ca.x - cb.x, ca.y - cb.y)
        if mir: ob = affinity.scale(ob, -1, 1, origin=ca)
        for ang in (0, 90, 180, 270):
            if affinity.rotate(ob, ang, origin=ca).symmetric_difference(a.outer).area < SHAPE_TOL * a.outer.area:
                def f(x, mir=mir, ang=ang):
                    y = affinity.translate(x, ca.x - cb.x, ca.y - cb.y)
                    if mir: y = affinity.scale(y, -1, 1, origin=ca)
                    return affinity.rotate(y, ang, origin=ca)
                yield f


@gx_rule('GG08', 'Mortise shorter than the same mortise on the identical part')
def check(g):
    """Slot-and-tab furniture locates parts by tabs passing through mortises (through slots about one sheet thick),
    and the mortise is drawn to the tab's width plus clearance (Opendesk / AtFAB joint libraries, Digital Wood
    Joints). Copies of the same part carry the same mortises. When a part is identical to another one in the file
    but one of its sheet-thickness mortises is under 80 % of the length of the same mortise (same place, same
    width) on the twin, that copy cannot take its tab: the kit does not assemble without recutting, and forcing
    the tab splits the ply. Twins are matched by outline (rotation and mirroring allowed)."""
    th = g.thickness or g.thickness_est
    if not th: return
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid and p.inner]
    if len(parts) > 300: return
    def slots(p):
        out = []
        for i in p.inner:
            if i.area < 30 or not i.is_valid: continue
            ax = _ax(i)
            if ax and 0.9 * th <= ax[0] <= 1.4 * th and ax[1] >= 1.2 * ax[0] and i.area > 0.75 * ax[2].area:
                out.append((i, ax[0], ax[1]))
        return out
    S = {id(p): slots(p) for p in parts}
    for a in parts:
        sa = S[id(a)]
        if not sa: continue
        hit = None
        for b in parts:
            if a is b or not S[id(b)] or abs(a.outer.area - b.outer.area) > SHAPE_TOL * a.outer.area: continue
            for f in _poses(a, b):
                for j, wj, Lj in S[id(b)]:
                    m = f(j); cm = m.centroid
                    for i, wi, Li in sa:
                        if i.centroid.distance(cm) < POS_TOL and abs(wi - wj) < 0.5 and Li < SHORT * Lj \
                                and i.buffer(0.3).within(m.buffer(0.6)):
                            hit = (wi, Li, Lj); break
                    if hit: break
                if hit: break
            if hit: break
        if hit:
            yield Finding('GG08', 'error', '%.1f mm mortise is %.0f mm long here but %.0f mm on an identical part: '
                          'the tab will not go in' % hit, a.key)
