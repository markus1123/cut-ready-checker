"""GH01: an edge notch (slot-together / cross-halving) with sharp bottom corners in a file that draws relief on
its other slots for the same sheet."""
import math
from shapely.geometry import Point, Polygon
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


def _notches(p):
    """Slots open to the part edge, closed across their mouth -> list of (notch, mouth line, depth)."""
    o = Polygon(p.outer.exterior.coords)
    if not o.is_valid:
        return []
    c = o.buffer(MAX_W / 2, join_style=2).buffer(-MAX_W / 2, join_style=2)
    out = []
    for nt in _pieces(c.difference(o)):
        mouth = nt.exterior.difference(o.exterior.buffer(0.05))
        if mouth.is_empty:
            continue
        depth = max(mouth.distance(Point(xy)) for xy in nt.exterior.coords)
        out.append((nt, mouth, depth))
    return out


@gx_rule('GH01', 'Edge notch with sharp bottom corners where the file dog-bones its other slots for that sheet')
def check(g):
    """A router bit is round, so the two bottom corners of a slot-together edge notch are cut with at least the bit
    radius (3 mm with the 6 mm / 1/4" bits that cut furniture sheet). The mating part has square corners: it sits on
    those fillets and stops short, the joint never seats and the piece racks (Opendesk / WikiHouse design guides,
    Fab Academy CNC week, Fusion 360 Dogbone add-in). Whether the file or the CAM is responsible for the relief shows
    in the file: when it draws dog-bone / T-bone lobes on its slots or notches for a sheet, a notch of the same width
    (within 12 %) whose bottom corners are plain sharp 90-degree corners was missed and will not take its part.
    Files that draw no relief anywhere are left alone (their shop adds it in CAM). Only notches at least as deep as
    they are wide and at most 60 mm wide are judged; the mouth corners (outside corners, often flared) are ignored."""
    relieved, sharp = [], []
    for p in g.parts:
        for i in p.inner:
            s = _core(i)
            if s is None:
                continue
            w, core = s
            if not _fillets(i) and len(_lobes(i, core)) >= 2:
                relieved.append(w)
        for nt, mouth, depth in _notches(p):
            s = _core(nt)
            if s is None:
                continue
            w, core = s
            if depth < w:
                continue
            bottom = lambda x: mouth.distance(x.centroid) > 0.5 * depth
            fb = [x for x in _fillets(nt) if bottom(x)]
            lb = [x for x in _lobes(nt, core) if bottom(x)]
            if not fb and len(lb) >= 2:
                relieved.append(w)
            elif len(fb) >= 2 and not lb:
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
            yield Finding('GH01', 'error',
                          '%.1f mm edge notch has sharp bottom corners, but this file draws dog-bone relief on its '
                          'other %.1f mm slots: a %.0f mm bit leaves %.0f mm fillets there and the mating part will '
                          'not seat' % (w, m[0], 2 * BIT_R, BIT_R), p.key)
