"""GH10: one hole of a regular drilled row drilled to a different depth than the rest of the row."""
from fc.core import Finding
from fc.gx.core import gx_rule

R_MAX = 12.0        # drilled bores
LINE_TOL = 0.3      # mm off the row line still counts as on it
PITCH_TOL = 0.5     # mm: equal pitch within this
MIN_PITCH = 8.0     # closer bores are a cluster, not a row
MIN_ROW = 4         # holes in the row, incl. the odd one
DEPTH_TOL = 1.0     # mm of depth difference that is rounding; layer depths step by >= 2 mm in practice


@gx_rule('GH10', 'One hole of a regular drilled row is drilled to a different depth from the others')
def check(g):
    """A regular row of identical holes (bolt, dowel, shelf-pin or fitting line: same diameter, equal pitch on one
    line) takes identical hardware and is drilled to one depth. Layer-driven CAM (Opendesk TOP-HOLE-<d>MM-DIAM_<depth>MM,
    Vectric / Fusion layer drilling) drills each circle to its layer's depth, so a single row hole whose depth differs
    by more than 1 mm from all its identical row-mates was put on the wrong layer: shallower, its bolt does not pass,
    its dowel stands proud or its shelf pin falls out; deeper, it can break through the face. Only interior holes of
    rows of >= 4 equally spaced same-size holes with every other hole at one depth are judged."""
    for p in g.parts:
        bs = [f for f in p.features if f.op == 'hole' and f.r and f.r <= R_MAX and f.depth and f.geom is not None
              and not f.geom.is_empty]
        if len(bs) < MIN_ROW or len(bs) > 300:
            continue
        cs = [(f, f.geom.centroid) for f in bs]
        hit = None
        for a, ca in cs:
            near = sorted(((ca.distance(cb), b, cb) for b, cb in cs if b is not a and abs(a.r - b.r) <= 0.1),
                          key=lambda t: t[0])[:4]
            for d, b, cb in near:
                if d < MIN_PITCH:
                    continue
                ux, uy = (cb.x - ca.x) / d, (cb.y - ca.y) / d
                on = sorted((((c.x - ca.x) * ux + (c.y - ca.y) * uy, f) for f, c in cs
                             if abs(f.r - a.r) <= 0.1 and abs((c.x - ca.x) * -uy + (c.y - ca.y) * ux) < LINE_TOL),
                            key=lambda t: t[0])
                ts = [t for t, _ in on]
                k = min(range(len(ts)), key=lambda i: abs(ts[i]))
                lo = k
                while lo > 0 and abs((ts[lo] - ts[lo - 1]) - d) < PITCH_TOL: lo -= 1
                hi = k
                while hi < len(ts) - 1 and abs((ts[hi + 1] - ts[hi]) - d) < PITCH_TOL: hi += 1
                run = [f for _, f in on[lo:hi + 1]]
                if len(run) < MIN_ROW:
                    continue
                for o in run[1:-1]:
                    rest = [f for f in run if f is not o]
                    if max(f.depth for f in rest) - min(f.depth for f in rest) <= 0.1 and \
                            abs(o.depth - rest[0].depth) > DEPTH_TOL:
                        hit = (o, rest[0].depth, len(run))
                        break
                if hit:
                    break
            if hit:
                break
        if hit:
            o, dep, n = hit
            yield Finding('GH10', 'error',
                          'one hole of a %d-hole dia %.1f mm row is drilled %.1f mm deep while the others are %.1f mm: '
                          'it was put on the wrong drill layer' % (n, 2 * o.r, o.depth, dep), p.key)
