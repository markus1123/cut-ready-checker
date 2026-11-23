import math
from fc.core import Finding
from fc.gx.core import gx_rule

R_MAX = 40.0      # round openings up to Ø80: fitting bores, dowel / bolt / cam holes, rod and tube sockets.
                  # Bigger round cut-outs are decorative / cable openings where a flat is cosmetic, not a fit.
N_MIN = 7         # 7+ equal sides on a common circle = a circle approximation. Squares, pentagons and hexagons
                  # (captured-nut traps) are deliberate shapes.
N_MAX = 200
LOSS_MAX = 0.25   # mm the hole may lose on its diameter (inscribed vs nominal) before a fitting no longer goes in
ROUND_TOL = 0.03  # vertices within 3 % of the mean radius = all on one circle
EDGE_TOL = 1.3    # longest / shortest side: a regular polygon, not an arbitrary shape


def _vertices(poly):
    pts = list(poly.exterior.coords)[:-1]
    out = []
    for q in pts:
        if not out or math.dist(q, out[-1]) > 1e-3:
            out.append(q)
    if len(out) > 1 and math.dist(out[0], out[-1]) <= 1e-3:
        out.pop()
    v, n = [], len(out)
    for i in range(n):
        a, b, c = out[i - 1], out[i], out[(i + 1) % n]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cr) > 1e-6 * max(1.0, math.dist(a, b) * math.dist(b, c)):
            v.append(b)           # drop collinear points: only real corners count as facets
    return v


def _faceted(poly):
    """-> (sides, circumradius, inradius) if the opening is a regular polygon standing in for a circle, else None."""
    if poly is None or poly.is_empty or poly.geom_type != 'Polygon':
        return None
    v = _vertices(poly)
    n = len(v)
    if n < N_MIN or n > N_MAX:
        return None
    c = poly.centroid
    rs = [math.dist(q, (c.x, c.y)) for q in v]
    R = sum(rs) / n
    if R <= 0 or R > R_MAX or max(rs) - min(rs) > ROUND_TOL * R:
        return None
    es = [math.dist(v[i], v[(i + 1) % n]) for i in range(n)]
    if min(es) <= 0 or max(es) > EDGE_TOL * min(es):
        return None
    return n, R, R * math.cos(math.pi / n)


@gx_rule('G11', 'Round hole exported as a coarse polygon: its flats make it too small for the fitting')
def check(g):
    """A router cuts exactly the path in the file. A round hole exported as an n-sided polyline (SketchUp, Fusion
    or Inkscape DXF export with a coarse arc-to-line tolerance) is cut as a polygon whose flats sit inside the
    intended circle: the largest round thing that passes is the inscribed circle, 2*R*(1 - cos(pi/n)) smaller in
    diameter (8 sides: -7.6 %, Ø8 -> Ø7.4). Dowels, bolts, cam bolts and tube legs are fitted to about 0.1-0.2 mm
    (dowels are drilled at nominal, bolt holes at +0.5 mm on a hand-placed fit), so once the hole loses more than
    0.25 mm on its diameter the fitting jams or splits the board; round parts show visible flats
    (SendCutSend / Ponoko file prep: circles and arcs must be true curves, not segmented polylines).
    0.25 mm is 2.5x the 0.05 mm chord tolerance arcs and bulged polylines are flattened with when the file is read,
    so true curves never reach it, and a 24+-segment export of a small fitting hole stays under it.
    Only through openings up to Ø80 with 7 or more equal sides on one circle are judged: hexagons and squares are
    deliberate nut traps / square holes, and big round cut-outs carry no fitting."""
    for p in g.parts:
        worst = None
        for i in p.inner:
            f = _faceted(i)
            if f is None:
                continue
            n, R, r_in = f
            loss = 2 * (R - r_in)
            if loss > LOSS_MAX and (worst is None or loss > worst[0]):
                worst = (loss, n, R, r_in)
        if worst:
            loss, n, R, r_in = worst
            yield Finding('G11', 'error',
                          'Ø%.1f hole is drawn as a %d-sided polygon, not a true circle: its flats leave only '
                          'Ø%.1f (%.2f mm under, limit %.2f) and the dowel/bolt will not go in'
                          % (2 * R, n, 2 * r_in, loss, LOSS_MAX), p.key)
