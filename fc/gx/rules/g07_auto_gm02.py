from fc.gx import limits
import math
from shapely.geometry import Point, Polygon
from fc.core import Finding
from fc.gx.core import gx_rule

BIT_R = limits.CONTOUR_R         # 6 mm (1/4") end mill: the smallest bit that cuts 12-24 mm furniture sheet through in sane time.
                    # Any inside corner sharper than this radius is left with a fillet of material by the bit.
FILLET = 0.5 * (1 - math.pi / 4) * BIT_R ** 2   # half the material a 3 mm-radius bit leaves in a 90-degree corner
LOBE_MIN = 4.0      # mm^2 of drawn relief (dog-bone / T-bone lobes) beyond the core rectangle: below that it is noise
MATCH = 0.12        # slots within 12 % (min 1 mm) of each other's width take the same sheet
MAX_W = 60.0        # wider openings are cut-outs (handles, cable holes), not slots for a mating sheet


def _axes(poly):
    r = poly.minimum_rotated_rectangle
    if r.geom_type != 'Polygon':
        return None
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return r, min(a, b), max(a, b)


def _pieces(d):
    if d.is_empty:
        return []
    return [x for x in getattr(d, 'geoms', [d]) if x.geom_type == 'Polygon' and not x.is_empty]


def _corner_fillets(hole):
    """Inside corners of an opening that a BIT_R bit cannot reach (one piece per sharp corner)."""
    o = hole.buffer(-BIT_R, join_style=1).buffer(BIT_R, join_style=1)
    return [x for x in _pieces(hole.difference(o)) if x.area > FILLET]


def _notches(p):
    """Slots open to the part edge (cross-halving / edge slots), as polygons closed across their mouth."""
    o = Polygon(p.outer.exterior.coords)
    if not o.is_valid:
        return []
    c = o.buffer(MAX_W / 2, join_style=2).buffer(-MAX_W / 2, join_style=2)
    return _pieces(c.difference(o))


def _lobes(i, core):
    """Relief lobes: pieces of the opening outside its core rectangle that are big enough to be a bit's path
    (clearly more than the corner rounding the core extraction itself leaves in a sharp corner)."""
    ax = _axes(i)
    rr = min(0.3 * ax[1], 6.0) if ax else 0
    return [x for x in _pieces(i.difference(core)) if x.area >= (1 - math.pi / 4) * rr * rr + LOBE_MIN / 2]


def _slot(i):
    """-> (core width, core length, lobe area, opening area / its bounding rectangle) for a rectangle-like opening."""
    if i.is_empty or i.geom_type != 'Polygon' or i.area < 30:
        return None
    ax = _axes(i)
    if ax is None or ax[1] < 2 * BIT_R or ax[1] > MAX_W + 10:
        return None
    rr = min(0.3 * ax[1], 6.0)
    core = i.buffer(-rr).buffer(rr)                  # morphological opening strips the dog-bone lobes
    if core.is_empty or core.geom_type != 'Polygon':
        return None
    cx = _axes(core)
    if cx is None or cx[1] <= 0:
        return None
    rc, w, L = cx
    if core.area < 0.85 * rc.area or w > MAX_W:
        return None
    return w, L, core, i.area / ax[0].area


@gx_rule('G07', 'Slot with sharp inside corners where the same file dog-bones its other slots for that sheet')
def check(g):
    """A router bit is round: every inside corner of a through slot is cut with at least the bit radius (3 mm for
    the 6 mm / 1/4" end mills that cut furniture sheet). A square tab or the square edge of the mating sheet then
    bottoms on those fillets and the joint does not close (Opendesk / WikiHouse design guides, Fab Academy CNC week,
    Fusion 360 Dogbone add-in). So receiving corners need drawn relief - dog-bones or T-bones - unless the CAM adds
    it. Which of the two a file relies on shows in the file itself: when it draws relief lobes on its slots for a
    given sheet (edge slots or closed mortises), its relief is in the drawing, not in the CAM, and a slot of the same
    width (same mating sheet, within 12 %) left as a plain sharp rectangle is cut with fillets and will not take
    its part. Files that draw no relief at all are left alone: their shop adds it in CAM (Fellesverkstedet
    `no_dogbones` exports, many Fab Academy files), which is a legitimate workflow and cannot be judged from geometry.
    Only closed rectangular through openings with all four corners sharp are judged; openings wider than 60 mm are
    cut-outs, not slots."""
    relieved = []                     # core widths of slots that carry drawn relief
    sharp = []                        # (part, width) of closed slots with four sharp corners
    for p in g.parts:
        for i in p.inner:
            s = _slot(i)
            if s is None:
                continue
            w, L, core, fill = s
            n = len(_corner_fillets(i))
            if n == 0 and len(_lobes(i, core)) >= 2:
                relieved.append(w)
            elif n >= 4 and fill > 0.99:
                sharp.append((p, w))
        o = Polygon(p.outer.exterior.coords)
        for nt in _notches(p):
            s = _slot(nt)
            if s is None:
                continue
            w, L, core, fill = s
            # The mouth of an edge slot is open (its corners are outside corners of the part, often flared as a
            # lead-in): only what sits at the bottom, away from the mouth, says whether the drawing carries relief.
            mouth = nt.exterior.difference(o.exterior.buffer(0.05))
            if mouth.is_empty:
                continue
            depth = max(mouth.distance(Point(c)) for c in nt.exterior.coords)
            if depth < w:
                continue
            bottom = lambda x: mouth.distance(x.centroid) > 0.5 * depth
            if not any(bottom(x) for x in _corner_fillets(nt)) and \
                    len([x for x in _lobes(nt, core) if bottom(x)]) >= 2:
                relieved.append(w)
    if not relieved or not sharp:
        return
    done = set()
    for p, w in sharp:
        if p.key in done:
            continue
        m = [r for r in relieved if abs(r - w) <= max(1.0, MATCH * r)]
        if m:
            done.add(p.key)
            yield Finding('G07', 'error',
                          '%.1f mm slot has sharp inside corners, but this file draws dog-bone relief on its other '
                          '%.1f mm slots: a %.0f mm bit leaves %.0f mm fillets here and the mating part will not seat'
                          % (w, m[0], 2 * BIT_R, BIT_R), p.key)
