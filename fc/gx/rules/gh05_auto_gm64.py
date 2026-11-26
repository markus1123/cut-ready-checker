"""GH05: one hole of a regular drilled row drawn at a different diameter from the rest of the row."""
from fc.core import Finding
from fc.gx.core import gx_rule

R_MAX = 12.0        # drilled bores
LINE_TOL = 0.3      # mm off the row line still counts as on it (drawing rounding)
PITCH_TOL = 0.5     # mm: equal pitch within this
MIN_PITCH = 8.0     # closer bores are a cluster, not a row
MIN_ROW = 4         # holes in the row, incl. the odd one: 3 identical neighbours make a row's size unambiguous
DIA_TOL = 0.75      # mm of diameter difference that is drawing noise; drill sizes step by >= 1 mm in furniture


def _bores(p):
    return [f for f in p.features if f.op == 'hole' and f.r and f.r <= R_MAX and f.geom is not None
            and not f.geom.is_empty]


@gx_rule('GH05', 'One hole of a regular drilled row has a different diameter from the others')
def check(g):
    """A regular row of holes (shelf pins, System 32 line, a hinge or runner screw line: equal pitch on one line)
    takes identical pins or screws, drilled with one tool. When every hole of such a row is one size and a single
    hole inside it is a different size (by >= 0.75 mm in diameter), that hole was resized or swapped by mistake:
    oversize it leaves the pin or screw loose, undersize the pin will not go in (Hettich Ratgeber Möbeltechnik:
    System 32 = Ø5 at 32 mm pitch; Häfele shelf supports). Only interior holes of rows of >= 4 equally spaced
    holes with all the others identical are judged; the end holes of a line often take other hardware."""
    for p in g.parts:
        bs = _bores(p)
        if len(bs) < MIN_ROW or len(bs) > 300:
            continue
        cs = [(f, f.geom.centroid) for f in bs]
        hit = None
        for a, ca in cs:
            near = sorted(((ca.distance(cb), b, cb) for b, cb in cs if b is not a and abs(a.r - b.r) <= 0.1),
                          key=lambda t: t[0])[:4]       # a row's pitch is set by one of a hole's nearest twins
            for d, b, cb in near:
                if d < MIN_PITCH:
                    continue
                ux, uy = (cb.x - ca.x) / d, (cb.y - ca.y) / d
                on = sorted((((c.x - ca.x) * ux + (c.y - ca.y) * uy, f) for f, c in cs
                             if abs((c.x - ca.x) * -uy + (c.y - ca.y) * ux) < LINE_TOL), key=lambda t: t[0])
                ts = [t for t, _ in on]
                k = min(range(len(ts)), key=lambda i: abs(ts[i]))
                # walk the run of equal pitch through a
                lo = k
                while lo > 0 and abs((ts[lo] - ts[lo - 1]) - d) < PITCH_TOL: lo -= 1
                hi = k
                while hi < len(ts) - 1 and abs((ts[hi + 1] - ts[hi]) - d) < PITCH_TOL: hi += 1
                run = [f for _, f in on[lo:hi + 1]]
                if len(run) < MIN_ROW:
                    continue
                odd = [f for f in run if abs(f.r - a.r) > DIA_TOL / 2]
                same = [f for f in run if abs(f.r - a.r) <= 0.1]
                if len(odd) == 1 and len(same) == len(run) - 1 and odd[0] is not run[0] and odd[0] is not run[-1]:
                    hit = (odd[0], a.r, len(run), d)
                    break
            if hit:
                break
        if hit:
            f, r, n, d = hit
            yield Finding('GH05', 'error',
                          'one hole of a %d-hole row at %.1f mm pitch is dia %.1f mm while the others are dia %.1f mm: '
                          'its pin / screw will be loose or will not fit' % (n, d, 2 * f.r, 2 * r), p.key)
