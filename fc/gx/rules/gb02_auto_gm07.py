import numpy as np
from fc.core import Finding
from fc.gx.core import gx_rule

R_MAX = 12.0       # drilled bores: screw pilots / clearance holes, dowels, shelf pins, bolts
LINE_TOL = 0.3     # mm: a hole within this of the line is on it (CAD / export rounding)
MIN_ON = 4         # holes on the line needed before it counts as a screw / fitting line (not a chance alignment)
MIN_SEP = 8.0      # mm: closer bores are a cluster / counterbore, not a line
OFF_MIN = 2.0      # mm: fittings and screws into an 18 mm edge tolerate about +-1 mm; 2 mm is clearly off
OFF_MAX = 10.0     # mm: further off is a hole on a line of its own, not a misplaced one
REPEAT_TOL = 0.2   # mm: the same offset on another hole of the part = deliberate stagger / zig-zag
MAX_HOLES = 150    # guard: perforated decorative panels are not drilled screw lines


def _misplaced(pts):
    """pts: (n, 2) array of same-size bore centres. -> list of (hole index, offset, n on line) for holes that lie
    inside the span of a straight line of >= MIN_ON holes but OFF_MIN..OFF_MAX beside it."""
    n = len(pts)
    out, seen = [], set()
    for i in range(n):
        for j in range(i + 1, n):
            if (i, j) in seen:
                continue
            v = pts[j] - pts[i]
            d = float(np.hypot(*v))
            if d < MIN_SEP:
                continue
            u = v / d
            rel = pts - pts[i]
            t = rel @ u
            o = np.abs(rel[:, 0] * u[1] - rel[:, 1] * u[0])
            on = np.where(o <= LINE_TOL)[0]
            for a in on:
                for b in on:
                    if a < b: seen.add((int(a), int(b)))
            if len(on) < MIN_ON:
                continue
            lo, hi = t[on].min(), t[on].max()
            for h in np.where((o >= OFF_MIN) & (o <= OFF_MAX) & (t > lo + MIN_SEP) & (t < hi - MIN_SEP))[0]:
                out.append((int(h), float(o[h]), len(on)))
    return out


@gx_rule('GB02', 'Hole of a straight screw / fitting line drawn off the line')
def check(g):
    """Screws that go into the edge of a mating panel, and the screws of a runner, hinge plate or rail, sit on ONE
    straight line: the centre line of the 12-24 mm edge they enter, or the screw line of the fitting. The spacing
    along the line is free (Opendesk desks put 4-6 screws at 414/450 mm along a leg), but sideways there is no
    slack: an 18 mm edge leaves 9 mm each side of a Ø4-6 screw, so a screw 2+ mm off line leaves 2-4 mm of edge
    wall and splits it or breaks out of the face, and a fitting's slots no longer line up. Fittings and pin holes
    tolerate about +-1 mm (built files: <= 1 mm). So when >= 4 same-size holes of a part lie exactly on one line
    and another hole of that size, BETWEEN the end holes, sits 2-10 mm beside it, that hole is misdrawn. Holes
    further off are on a line of their own. If the same offset recurs on another hole of the part (zig-zag or
    staggered screw pattern, Opendesk Standing Desk splayed end holes) it is the design, not a slip."""
    for p in g.parts:
        by_r = {}
        for f in p.features:
            if f.op == 'hole' and f.r and f.r <= R_MAX and f.geom is not None and not f.geom.is_empty:
                c = f.geom.centroid
                by_r.setdefault(round(f.r, 1), []).append((c.x, c.y))
        worst = None
        for r, cs in by_r.items():
            if len(cs) < MIN_ON + 1 or len(cs) > MAX_HOLES:
                continue
            pts = np.array(cs, dtype=float)
            hits = _misplaced(pts)
            for h, o, non in hits:
                if any(h2 != h and abs(o2 - o) <= REPEAT_TOL for h2, o2, _ in hits):
                    continue
                if worst is None or o > worst[1]:
                    worst = (r, o, non)
        if worst:
            r, o, non = worst
            yield Finding('GB02', 'error',
                          'hole r=%.1f sits %.1f mm beside a straight line of %d same-size holes: the screw misses the '
                          'centre of the mating edge / the fitting\'s screw line (tolerance ~1 mm)' % (r, o, non), p.key)
