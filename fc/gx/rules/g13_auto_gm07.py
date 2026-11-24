import math
from fc.core import Finding
from fc.gx.core import gx_rule

R_MAX = 12.0       # drilled bores: shelf pins, screw pilots/clearance, dowels, cam bolts
LINE_TOL = 0.3     # mm: holes within this of the line are "on" it (CAD/export rounding)
PITCH_TOL = 0.5    # mm: equal pitch within this (drawing rounding, not a different spacing)
MIN_PITCH = 8.0    # mm: closer bores are a cluster / counterbore, not a row
FIT_TOL = 1.0      # mm: what pin holes / fitting screw slots tolerate off the line (built designs: <= 1.0)
OFF_MIN = 2.0      # mm: FIT_TOL + CNC/drawing slack; beyond this the row hole no longer lines up
OFF_MAX = 10.0     # mm: further off is a separate hole on its own line, not a misplaced row hole
REPEAT_TOL = 0.2   # mm: an offset repeated on another hole of the part is a deliberate stagger, not a slip
MAX_HOLES = 400    # guard: huge perforated panels are decoration, not drilled rows


def _bores(p):
    out = []
    for f in p.features:
        if f.op == 'hole' and f.r and f.r <= R_MAX and f.geom is not None and not f.geom.is_empty:
            c = f.geom.centroid
            out.append((c.x, c.y, round(f.r, 1)))
    return out


def _scan(pts):
    """-> (straight_rows, offenders). straight_rows: set of (r, pitch_mm_rounded, run_length) for runs of >= 3
    same-size bores all on one line at one pitch. offenders: (offset, run_len, on_count, pitch, r) for a bore that
    sits at a free pitch position of such a run but OFF_MIN..OFF_MAX beside its line."""
    rows, offs, members = set(), [], set()
    n = len(pts)
    for i in range(n):
        a = pts[i]
        for j in range(n):
            c = pts[j]
            if i == j or a[2] != c[2]:
                continue
            d = math.hypot(c[0] - a[0], c[1] - a[1])
            if d < MIN_PITCH:
                continue
            ux, uy = (c[0] - a[0]) / d, (c[1] - a[1]) / d
            on, near = {}, []
            for h, b in enumerate(pts):
                if b[2] != a[2]:
                    continue
                dx, dy = b[0] - a[0], b[1] - a[1]
                t = dx * ux + dy * uy
                k = round(t / d)
                if abs(t - k * d) > PITCH_TOL:
                    continue                      # not at a pitch position of this row
                o = abs(dy * ux - dx * uy)
                if o <= LINE_TOL:
                    on[k] = h
                elif OFF_MIN <= o <= OFF_MAX:
                    near.append((k, o, h))
            # a = position 0, c = position 1 (a pair of neighbours in the row sets the pitch)
            if -1 not in on:                      # straight run starting at a
                run = 0
                while run in on:
                    run += 1
                if run >= 3:
                    rows.add((a[2], round(d), run))
                    members.update(on[q] for q in range(run))
            for k, o, h in near:
                if k in on:
                    continue                      # that row position is already drilled; this is another bore
                lo, hi = k, k
                while lo - 1 in on: lo -= 1
                while hi + 1 in on: hi += 1
                if hi - lo + 1 >= 3:              # run of >= 3 positions, all drilled, one of them off the line
                    offs.append((o, hi - lo + 1, hi - lo, d, a[2], h, frozenset(on[q] for q in range(lo, hi + 1) if q != k)))
    offs = [x for x in offs if x[5] not in members]   # a hole on a straight row is not the stray one
    return rows, offs


@gx_rule('G13', 'One hole of a regular drilled row is off the row line')
def check(g):
    """A drilled row (>= 3 same-size holes on one straight line at one pitch: System 32 / shelf-pin lines,
    runner and hinge-plate screw lines, the screw line along a mating panel's edge) is drilled from one reference
    edge with one jig or one CNC line because whatever goes into it is straight too: a shelf rests on four pins
    at one height, a drawer runner or hinge plate has its screw slots on one line, and screws into the 18 mm edge
    of a mating panel must hit its centre line (9 mm each side; a Ø4-6 screw 2+ mm off line leaves only a few mm
    of edge wall and splits it or breaks out of the face). Pin holes and fitting slots tolerate about +-1 mm, which
    is also what built designs in the corpus show (worst: 1.0 mm off a 4-hole screw row). So a hole of the same size
    at a free pitch position of an established row but 2-10 mm beside its line is a misdrawn row hole: the shelf
    rocks on three pins, the fitting cannot be screwed on straight, the screw misses the mating edge. Holes more
    than 10 mm off are on a line of their own (a second row, a different fitting).
    A row is established by >= 3 holes on the line. With only 2 on the line (a 3-hole row with one hole off) the
    pattern alone could be a deliberate triangle of screws, so it only counts when another part of the same file
    carries that row straight (same bore, same pitch, 3 on the line): parts drilled for the same fitting / mating
    panel must match, and the odd one out is the misdrawn one.
    A misdrawn hole is a one-off. When the same offset recurs on another hole of the part (Opendesk Standing Desk:
    the end hole of every staggered screw run is splayed 3.9 mm on purpose, at both ends of both legs) the
    offset is part of the design and the fitting is made to match it."""
    scans = []
    for p in g.parts:
        pts = _bores(p)
        if len(pts) < 3 or len(pts) > MAX_HOLES:
            scans.append((p, set(), []))
            continue
        rows, offs = _scan(pts)
        scans.append((p, rows, offs))
    for idx, (p, rows, offs) in enumerate(scans):
        valid = []
        for o, run, cnt, d, r, h, mem in offs:
            if cnt < 3:
                twin = any(rr == r and abs(pp - d) <= 1 and n >= run
                           for jdx, (q, rws, _) in enumerate(scans) if jdx != idx for rr, pp, n in rws)
                if not twin:
                    continue
            valid.append((o, run, d, r, h, mem))
        worst = None
        for o, run, d, r, h, mem in valid:
            if any(abs(o - o2) <= REPEAT_TOL and h2 != h and h2 not in mem and h not in mem2
                   for o2, _, _, _, h2, mem2 in valid):
                continue                          # same offset drawn on purpose on another hole of the part
            if worst is None or o > worst[0]:
                worst = (o, run, d, r)
        if worst:
            o, run, d, r = worst
            yield Finding('G13', 'error',
                          'hole r=%.1f of a %d-hole row (pitch %.0f mm) sits %.1f mm off the row line (fittings '
                          'tolerate ~%.0f mm): the shelf pin / fitting / screw into the mating edge no longer lines up'
                          % (r, run, d, o, FIT_TOL), p.key)
