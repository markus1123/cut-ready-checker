from fc.core import Finding
from fc.gx.core import gx_rule

R_MAX = 12.0      # mm: drilled / fitting holes; bigger round openings are cut-outs
LINE_TOL = 0.3    # mm: holes this close to the line through two others are on the row line
PITCH_TOL = 0.3   # mm: spacings equal within 0.3 mm are the same pitch (CNC drilling is accurate to ~0.1 mm)
OFF_MIN = 1.0     # mm: a shelf pin / runner screw / cam bolt tolerates < 1 mm (Minifix: +1 / -0.5 mm)
MIN_ROW = 4       # holes in a row: 3 regular spacings are needed to call a pitch


def _holes(p):
    out = []
    for f in p.features:
        if f.op != 'hole' or not f.r or f.r > R_MAX or f.geom is None: continue
        c = f.geom.centroid
        if any(q.distance(c) < 0.5 for q, r in out): continue      # concentric pilot + countersink = one hole
        out.append((c, f.r))
    return out


def _rows(hs):
    """Lines of >= MIN_ROW same-size holes -> list of (sorted positions along the line, holes)."""
    byr = {}
    for c, r in hs: byr.setdefault(round(r, 1), []).append(c)
    seen, out = set(), []
    for r, cs in byr.items():
        if len(cs) < MIN_ROW or len(cs) > 150: continue
        for i, a in enumerate(cs):
            for b in cs[i + 1:]:
                d = a.distance(b)
                if d < 5: continue
                ux, uy = (b.x - a.x) / d, (b.y - a.y) / d
                on = sorted(((c.x - a.x) * ux + (c.y - a.y) * uy, k) for k, c in enumerate(cs)
                            if abs((c.x - a.x) * -uy + (c.y - a.y) * ux) < LINE_TOL)
                key = (r, frozenset(k for _, k in on))
                if len(on) < MIN_ROW or key in seen: continue
                seen.add(key)
                out.append(([t for t, _ in on], [cs[k] for _, k in on], r))
    return out


@gx_rule('GK03', 'One hole of a regular drilled row off the row pitch')
def check(g):
    """System 32 lines, shelf-pin rows and runner / hinge-plate screw rows are drilled on ONE pitch (32 mm for System
    32; Hettich, Hafele) so the maker's pins, runners and plates fit them. When every spacing of a straight row of
    same-size holes is the same pitch P except around one hole - which sits 1 mm or more (up to P/3) off its grid
    position between two neighbours that are themselves 2P apart - that hole was nudged along the row: its shelf pin
    is out of level with the pins on the other side (the shelf rocks), or the runner / plate screw has no hole where
    the fitting has one. Fittings tolerate well under 1 mm (Minifix +1 / -0.5 mm)."""
    for p in g.parts:
        hs = _holes(p)
        if len(hs) < MIN_ROW: continue
        done = set()
        for ts, cs, r in _rows(hs):
            d = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
            for i in range(1, len(ts) - 1):           # interior hole i between spacings d[i-1] and d[i]
                rest = d[:i - 1] + d[i + 1:]
                if not rest: continue
                P = sorted(rest)[len(rest) // 2]
                if P < 8 or any(abs(x - P) > PITCH_TOL for x in rest): continue
                if abs(d[i - 1] + d[i] - 2 * P) > PITCH_TOL: continue
                off = abs(d[i - 1] - P)
                if not (OFF_MIN <= off <= P / 3): continue
                c = cs[i]
                k = (round(c.x), round(c.y))
                if k in done: continue
                done.add(k)
                yield Finding('GK03', 'error',
                              'the %.1f mm hole at (%.0f, %.0f) is %.1f mm off the %.1f mm pitch of its row of %d holes: '
                              'its pin / screw will not line up with the fitting or the matching row'
                              % (2 * r, c.x, c.y, off, P, len(ts)), p.key)
