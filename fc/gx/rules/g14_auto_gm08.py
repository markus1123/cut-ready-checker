import os
from shapely.geometry import LineString
from shapely.ops import unary_union, polygonize
from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx import model

MIN_LOBE_W = 1.0      # mm: a reversed lobe at least this wide is drawn geometry, not export noise
MAX_PTS = 20000       # guard: rings bigger than this are not checked (no furniture outline needs it)
_RAW = {}             # (path, units, mtime) -> [(cx, cy, layer, lobe_area, lobe_count)]


def _winding(ring, x, y):
    w = 0
    for (x0, y0), (x1, y1) in zip(ring[:-1], ring[1:]):
        if y0 <= y:
            if y1 > y and (x1 - x0) * (y - y0) - (x - x0) * (y1 - y0) > 0:
                w += 1
        elif y1 <= y and (x1 - x0) * (y - y0) - (x - x0) * (y1 - y0) < 0:
            w -= 1
    return w


def reversed_lobes(pts):
    """Closed contour (list of xy, mm) -> faces where the contour runs the WRONG way round (winding sign opposite
    to the body of the part) and that are at least MIN_LOBE_W wide. Empty for simple contours and for mere
    self-touches / doubled-back zero-area spurs (those enclose nothing reversed)."""
    ring = [tuple(p[:2]) for p in pts]
    if len(ring) < 4 or len(ring) > MAX_PTS:
        return []
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    ls = LineString(ring)
    if ls.is_simple:
        return []
    faces = [f for f in polygonize(unary_union(ls)) if f.area > 0]
    if len(faces) < 2:
        return []
    body = max(faces, key=lambda f: f.area)
    bp = body.representative_point()
    main = _winding(ring, bp.x, bp.y)
    if main == 0:
        return []
    out = []
    for f in faces:
        if f is body or f.buffer(-MIN_LOBE_W / 2).is_empty:
            continue
        rp = f.representative_point()
        if _winding(ring, rp.x, rp.y) * main < 0:
            out.append(f)
    return out


def _raw_entities(g):
    """Single closed DXF entities (one polyline/spline drawn closed) on cut layers, read through fc.gx.model.
    The parser repairs crossed loops with buffer(0) (or drops them), so a real figure-8 is only visible here.
    Loops the model stitched together from separate entities are NOT checked: greedy chaining through shared
    vertices can itself produce a crossing that is not in the drawing."""
    if not g.path or not os.path.isfile(g.path):
        return []
    k = (g.path, g.units, os.path.getmtime(g.path))
    if k in _RAW:
        return _RAW[k]
    s = model.SCALE.get(g.units, 1.0)
    eps = 0.02 / s
    key = lambda p: (round(p[0] / eps), round(p[1] / eps))
    out = []
    try:
        segs, _ = model._loops(g.path, 0.05 / s)
    except (IOError, OSError, ValueError, model.ezdxf.DXFError):
        segs = []
    for pts, layer in segs:
        if len(pts) < 4 or key(pts[0]) != key(pts[-1]) or not model.layer_op(layer)[0].startswith('cut'):
            continue
        lobes = reversed_lobes([(x * s, y * s) for x, y in pts])
        if lobes:
            c = LineString([(x * s, y * s) for x, y in pts]).centroid
            out.append((c.x, c.y, layer, sum(f.area for f in lobes), len(lobes)))
    _RAW[k] = out
    return out


def _msg(where, n, area):
    return ('%s crosses itself: %d lobe(s), %.0f mm2, run the wrong way round (>= %.0f mm wide). CAM cannot tell '
            'inside from outside there - the profile offset fails or cuts the wrong side (part skipped, oversize or '
            'gouged at the crossing)' % (where, n, area, MIN_LOBE_W))


@gx_rule('G14', 'Cut contour crosses itself (figure-8 / reversed lobe)')
def check(g):
    """A profile toolpath is the cut contour offset by the cutter radius to one side (outside for a part, inside
    for an opening). Which side is 'outside' is defined by the direction the closed contour runs. Where a contour
    crosses itself (figure-8 kink, overshoot that doubles back past its own line) it encloses a lobe that runs the
    opposite way: there inside and outside swap. VCarve/Aspire 'Validate vectors' rejects such vectors, Fusion/
    SheetCAM offset them into garbage, and the machine cuts the part oversize, skips it, or plunges through the
    part at the crossing. CAM join/offset tolerances (and our DXF flattening, 0.05 mm) swallow slivers, so the
    limit is a reversed lobe at least 1 mm wide - drawn geometry, not rounding. Mere self-touches (slots traced in
    and back out along the same line, outlines touching at one vertex) enclose no reversed area and are fine:
    built Opendesk files are full of them.
    Checked on the parsed part contours and, because the parser repairs crossed loops before rules see them, on
    every single closed entity of the raw DXF on a cut layer."""
    seen = set()
    for p in g.parts:
        for where, poly in [('part outline', p.outer)] + [('opening', i) for i in p.inner]:
            if poly is None or poly.geom_type != 'Polygon' or poly.is_empty:
                continue
            lobes = reversed_lobes(list(poly.exterior.coords))
            if lobes:
                seen.add(p.key)
                yield Finding('G14', 'error', _msg(where, len(lobes), sum(f.area for f in lobes)), p.key)
                break
    for cx, cy, layer, area, n in _raw_entities(g):
        k = (round(cx / 10), round(cy / 10))
        if k in seen:
            continue
        seen.add(k)
        yield Finding('G14', 'error', _msg('closed contour on %s' % layer, n, area), k)
