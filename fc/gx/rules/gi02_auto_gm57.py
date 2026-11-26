"""GI02: a narrow housing (one that takes a sheet edge / rail) missing on one of a pair of identical parts."""
import math
from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx.rules.gg09_auto_gm57 import MIN_PART, SHAPE_TOL, _poses, _feats, _match

MAX_W = 2.5   # x sheet thickness: housings this narrow take the edge of a sheet, a rail or a tenon


def _width(y):
    r = y.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return None
    c = list(r.exterior.coords)
    return min(math.dist(c[0], c[1]), math.dist(c[1], c[2]))


@gx_rule('GI02', 'A sheet-edge housing missing on one of two identical parts')
def check(g):
    """Paired parts (left / right sides, front / back rails) are machined alike: the housing on one side that takes
    a shelf, divider, rail or tenon has its partner on the other side at the same place, or the part it holds is
    supported at one end only. GG09 judges parts with two or more twins; here a PAIR is enough, but only for housings
    narrow enough to receive a sheet edge or rail (width <= 2.5 x sheet thickness, > 3 mm deep, >= 300 mm2): wide,
    shallow recesses (cable trays, label fields, decorative panels) can legitimately be on one copy only, narrow
    housings cannot - the shelf / rail that goes in them needs both ends held. The pair must otherwise match feature
    for feature (outline, every pocket and opening; mirroring and rotation allowed), so it is the same part with one
    housing lost on export (layer turned off, deleted as a duplicate)."""
    th = g.thickness or g.thickness_est
    if not th: return
    parts = [p for p in g.parts if p.outer.area > MIN_PART and p.outer.is_valid]
    if len(parts) > 300: return
    F = {id(p): _feats(p, th) for p in parts}
    for a in parts:
        fa = F[id(a)]
        for b in parts:
            fb = F[id(b)]
            if a is b or len(fb) != len(fa) + 1 or len(fb) < 2: continue
            if abs(a.outer.area - b.outer.area) > SHAPE_TOL * a.outer.area: continue
            hit = None
            for f in _poses(a, b):
                hit = _match(fa, [(k, f(y), j) for k, y, j in fb])
                if hit: break
            if not hit or hit[0] != 'pocket': continue
            w = _width(hit[1])
            if w is None or w > MAX_W * th: continue
            yield Finding('GI02', 'error', 'its identical twin has a %.0f mm wide housing (pocket, %.0f mm2) here that '
                          'this copy lacks, all other features match: the shelf / rail it takes is held at one end only'
                          % (w, hit[1].area), a.key)
            break
