"""Dowel joints: the two holes a dowel sits in must add up to a dowel length you can buy, plus glue space."""
from fc.core import rule, Finding
from fc.world import frames, holes, inside, add, mul, dot

# Standard fluted beech dowel lengths per diameter (Häfele / Würth / Wolfcraft ranges).
DOWELS = {5: (20, 25, 30), 6: (25, 30, 35, 40), 8: (30, 35, 40, 50), 10: (30, 40, 50, 60), 12: (40, 50, 60)}
GAP_MIN, GAP_MAX = 1.0, 4.0     # glue/air space: face depth + edge depth = dowel length + 1..4 mm
MIN_WALL = 4.0                  # a face hole must leave at least this much board under it
TOL = 0.6


def _is_dowel(o):
    return o['note'].startswith('Plugg')


@rule('R13', 'Dowel joints: face + edge hole depth = a standard dowel length + 1-4 mm glue space')
def check(d):
    """Workshop reason: a dowel joint is only drawn tight if the dowel fits the two holes it sits in. The face hole
    depth plus the edge hole depth must be the dowel length plus 1-4 mm for glue and air. If the sum is shorter than
    the shortest dowel sold for that diameter (e.g. 12 + 15 = 27 mm for Ø8, where dowels come as 8x30/35/40), the
    dowel bottoms out and the carcass joint stays open by the difference; the Minifix cams cannot pull it closed
    either and the edge splits when the operator forces it. If the sum is far longer than any dowel the joint is
    loose and the hole pattern does not match a dowel anyone can buy. A face hole that leaves less than ~4 mm of board
    under it blows out or telegraphs through the visible face."""
    inst = frames(d)
    out, seen = [], set()
    for f in inst:
        t = f['part']['t']
        for h in holes(f):
            o = h['op']
            if not _is_dowel(o):
                continue
            if h['end'] != 'edge':
                try:
                    depth = float(h['depth'])
                except (TypeError, ValueError):
                    continue
                if t - depth < MIN_WALL:
                    key = (f['code'], 'wall', depth)
                    if key not in seen:
                        seen.add(key)
                        out.append(Finding('R13', 'error', '%s: dowel face hole Ø%g is %g mm deep in %.1f mm board, '
                                           'leaves %.1f mm (need >= %g).' % (f['code'], h['d'], depth, t, t - depth,
                                                                              MIN_WALL), f['code']))
                continue
            probe = add(h['entry'], mul(h['dir'], -0.5))
            mates = [g for g in inst if g is not f and inside(g['box'], probe)]
            mate = None
            for g in mates:
                for gh in holes(g):
                    if _is_dowel(gh['op']) and gh['end'] != 'edge' and dot(gh['dir'], h['dir']) < -0.99:
                        dv = [a - b for a, b in zip(gh['entry'], h['entry'])]
                        if sum(v * v for v in dv) ** 0.5 < TOL:
                            mate = (g, gh)
                            break
                if mate:
                    break
            if not mate:
                continue  # an unpaired dowel hole is R03's business
            g, gh = mate
            total = float(h['depth']) + float(gh['depth'])
            dia = round(float(h['d']))
            lengths = DOWELS.get(dia)
            key = (f['code'], g['code'], round(total, 1), dia)
            if key in seen:
                continue
            if lengths is None:
                seen.add(key)
                out.append(Finding('R13', 'error', '%s -> %s: dowel Ø%g is not a standard dowel diameter (%s).'
                                   % (f['code'], g['code'], h['d'], '/'.join(map(str, sorted(DOWELS)))), f['code']))
                continue
            fits = [L for L in lengths if L + GAP_MIN <= total + 1e-6 and total - L <= GAP_MAX + 1e-6]
            if fits:
                continue
            seen.add(key)
            shorter = [L for L in lengths if L + GAP_MIN > total + 1e-6]
            if total < lengths[0] + GAP_MIN:
                why = 'shorter than the shortest Ø%d dowel (%dx%d) + %g mm: it bottoms out and the joint stays ' \
                      '%.1f mm open' % (dia, dia, lengths[0], GAP_MIN, lengths[0] + GAP_MIN - total)
            else:
                why = 'matches no Ø%d dowel (%s) with %g-%g mm glue space' % (
                    dia, '/'.join(str(L) for L in lengths), GAP_MIN, GAP_MAX)
            out.append(Finding('R13', 'error', '%s -> %s: dowel holes %g (edge) + %g (face) = %g mm, %s.'
                               % (f['code'], g['code'], float(h['depth']), float(gh['depth']), total, why), f['code']))
    return out
