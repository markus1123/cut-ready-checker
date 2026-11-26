"""GH07: an edge notch (slot-together / cross-halving) with sharp bottom corners in a file that draws relief on
its other slots for the same sheet."""
import math
from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx import limits

BIT_R = limits.CONTOUR_R            # radius of the usual contour bit (6 mm / 1/4"): what an inside corner is left with
FILLET = 0.5 * (1 - math.pi / 4) * BIT_R ** 2   # half the material such a bit leaves in a 90-degree corner
LOBE_MIN = 4.0                      # mm^2 of drawn relief beyond the core rectangle: less is drawing noise
MATCH = 0.12                        # slot widths within 12 % (min 1 mm) take the same mating sheet
MAX_W = 60.0                        # wider openings are cut-outs, not slots for a mating sheet


def _pieces(d):
    if d.is_empty:
        return []
    return [x for x in getattr(d, 'geoms', [d]) if x.geom_type == 'Polygon' and not x.is_empty]


def _axes(poly):
    r = poly.minimum_rotated_rectangle
    if r.geom_type != 'Polygon':
        return None
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return r, min(a, b), max(a, b)


def _fillets(hole):
    """Inside corners of an opening that a BIT_R bit cannot reach."""
    o = hole.buffer(-BIT_R, join_style=1).buffer(BIT_R, join_style=1)
    return [x for x in _pieces(hole.difference(o)) if x.area > FILLET]


def _core(i):
    """-> (core width, core polygon) of a rectangle-like opening (dog-bone lobes stripped), or None."""
    if i.is_empty or i.geom_type != 'Polygon' or i.area < 30:
        return None
    ax = _axes(i)
    if ax is None or ax[1] < 2 * BIT_R or ax[1] > MAX_W + 10:
        return None
    rr = min(0.3 * ax[1], 6.0)
    core = i.buffer(-rr).buffer(rr)
    if core.is_empty or core.geom_type != 'Polygon':
        return None
    cx = _axes(core)
    if cx is None or cx[1] <= 0 or core.area < 0.85 * cx[0].area or cx[1] > MAX_W:
        return None
    return cx[1], core


def _lobes(i, core):
    ax = _axes(i)
    rr = min(0.3 * ax[1], 6.0) if ax else 0
    return [x for x in _pieces(i.difference(core)) if x.area >= (1 - math.pi / 4) * rr * rr + LOBE_MIN / 2]


def _housings(p):
    """Rectangle-like blind pockets (housings / dados) of a part, as polygons."""
    return [f.geom for f in p.features if f.op == 'pocket' and not f.r and f.geom is not None
            and f.geom.geom_type == 'Polygon' and not f.geom.is_empty]


@gx_rule('GH07', 'Housing pocket with sharp corners where the file dog-bones its other housings for that sheet')
def check(g):
    """A pocketing bit is round, so every corner of a housing (dado / trench a shelf or divider sits in) keeps at
    least the bit radius (3 mm with a 6 mm / 1/4" bit). The square edge and ends of the mating sheet bottom on
    those fillets: the part stands proud, the joint does not close and the glue line starves (Opendesk design
    guidelines; Fusion 360 Dogbone add-in, which treats pockets like slots). When a file draws dog-bone / T-bone
    lobes on its housings for a sheet, its relief is in the drawing, not the CAM: a housing of the same width (within
    12 %) left as a plain sharp rectangle (all four corners sharp) was missed and will not take its part. Files that
    draw no relief on any housing are left alone (their shop relieves corners in CAM)."""
    relieved, sharp = [], []
    for p in g.parts:
        for h in _housings(p):
            s = _core(h)
            if s is None:
                continue
            w, core = s
            fl = _fillets(h)
            if not fl and len(_lobes(h, core)) >= 2:
                relieved.append(w)
            elif len(fl) >= 4 and h.area > 0.99 * _axes(h)[0].area:
                sharp.append((p, w))
    if not relieved or not sharp:
        return
    done = set()
    for p, w in sharp:
        if p.key in done:
            continue
        m = [r for r in relieved if abs(r - w) <= max(1.0, MATCH * r)]
        if m:
            done.add(p.key)
            yield Finding('GH07', 'error',
                          '%.1f mm housing pocket has sharp corners, but this file dog-bones its other %.1f mm '
                          'housings: a %.0f mm bit leaves %.0f mm fillets there and the mating part stands proud'
                          % (w, m[0], 2 * BIT_R, BIT_R), p.key)
