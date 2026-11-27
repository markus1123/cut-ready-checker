import math
from fc.core import Finding
from fc.gx.core import gx_rule

AREA = (3.0, 3000.0)   # mm2: drilled-hole sized loops (about 2-60 mm across)
RATIO = (1.01, 1.12)   # long / short axis: a drill makes round holes (< 1 % out); a 1-12 % stretch is a scale error
SAME_RATIO = 0.008     # the stretched holes all share one ratio ...
SAME_ANGLE = 3.0       # ... and one long-axis direction (degrees)
MIN_N = 4              # at least this many, and they must be most of the file's round-ish loops


def _ovals(g):
    """Near-round closed loops (openings and features drawn as polygons, not as circle entities):
    -> list of (part, ratio, long-axis angle mod 180)."""
    out, n_round = [], 0
    for p in g.parts:
        geoms = list(p.inner) + [f.geom for f in p.features if f.geom is not None and f.geom not in p.inner and not f.r]
        n_round += sum(1 for f in p.features if f.op == 'hole' and f.r)
        for q in geoms:
            if q.geom_type != 'Polygon' or not (AREA[0] <= q.area <= AREA[1]) or len(q.exterior.coords) < 13: continue
            r = q.minimum_rotated_rectangle
            if r.geom_type != 'Polygon': continue
            c = list(r.exterior.coords)
            a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
            w, L = min(a, b), max(a, b)
            if w <= 0 or abs(q.area - math.pi / 4 * w * L) > 0.03 * q.area: continue      # not an ellipse
            n_round += 1
            k = L / w
            if not (RATIO[0] <= k <= RATIO[1]): continue
            i0, i1 = (0, 1) if a >= b else (1, 2)
            ang = math.degrees(math.atan2(c[i1][1] - c[i0][1], c[i1][0] - c[i0][0])) % 180
            out.append((p, k, ang))
    return out, n_round


@gx_rule('GK07', 'Round holes drawn as ellipses all stretched the same way (non-uniform scale)')
def check(g):
    """A drill and a router bit make round holes; a file whose small round loops are ALL ellipses stretched by the same
    1-12 % in the same direction has been scaled non-uniformly (an SVG / PDF viewBox or DPI mismatch, a scale with
    'uniform' unticked, X and Y steps-per-mm calibrated differently in the drawing step): every part is that much
    too long one way, so joints and sheet sizes are off and dowels / bolts / pins do not fit their oval holes.
    Drawn decorative ellipses vary in ratio and direction; a scale error stretches every hole identically."""
    ov, n_round = _ovals(g)
    if len(ov) < MIN_N: return
    best = None
    for _, k0, a0 in ov:
        grp = [t for t in ov if abs(t[1] - k0) <= SAME_RATIO and min(abs(t[2] - a0), 180 - abs(t[2] - a0)) <= SAME_ANGLE]
        if best is None or len(grp) > len(best[0]): best = (grp, k0, a0)
    grp, k0, a0 = best
    if len(grp) < MIN_N or len(grp) < 0.6 * n_round: return
    seen = set()
    for p, k, a in grp:
        if id(p) in seen: continue
        seen.add(id(p))
        yield Finding('GK07', 'error',
                      '%d of the file\'s %d round holes are ellipses stretched %.1f %% along %.0f deg: the drawing was '
                      'scaled non-uniformly - parts are that much too long one way and holes are oval'
                      % (len(grp), n_round, 100 * (k0 - 1), a0), p.key)
