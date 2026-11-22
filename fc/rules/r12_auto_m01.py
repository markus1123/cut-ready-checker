"""Minifix housing distance must match the bolt system the edge hole is drilled for."""
from fc.core import rule, Finding

# Minifix 15 / 12 cam connectors come in fixed drilling-distance systems: the housing centre sits B mm from the
# joint edge, and the connecting bolt (screwed into the mating panel's face) is made so its head lands exactly B mm
# from that face, i.e. in the middle of the cam. Häfele template: edge hole Ø8 drilled ~B + 10 deep
# (B24 -> 34 mm, B34 -> 44 mm) so it runs right across the housing.
SYSTEMS = (24, 34)
TOL = 0.5


def _edge_dist(p, o, e):
    """Distance from the named edge to a face hole o of part p, and o's coordinate along that edge."""
    if e.endswith('venstre ende'):
        return o['x'], o['y']
    if e.endswith('høyre ende'):
        return p['L'] - o['x'], o['y']
    if e.endswith('underkant'):
        return o['y'], o['x']
    if e.endswith('overkant'):
        return p['B'] - o['y'], o['x']
    return None, None


@rule('R12', 'Minifix housing distance from the edge is a standard system (B24/B34) and matches the bolt-hole depth')
def check(d):
    """Workshop reason: a Minifix joint only pulls tight when the cam housing centre is exactly where the bolt head
    ends up. The bolt length is fixed by the system (B24 or B34) and the Ø8 edge hole is drilled for that bolt: it
    must run at least across the whole housing (depth >= B + housing radius) for the head to enter the cam. If the
    housing is drilled for one system and the edge hole/bolt for another (e.g. housing at 34 mm, edge hole 34 mm deep
    = B24 bolt), the cam turns past the bolt head, the joint never closes, and the operator cracks the chipboard
    trying. A housing distance that is not a standard system cannot be matched by any bolt you can buy."""
    out, seen = [], set()
    for p in d.parts:
        houses = [o for o in p['ops'] if o['kind'] == 'hole' and 'minifix-hus' in o['note'].lower()]
        for e in p['ops']:
            if e['kind'] != 'edge' or 'minifix' not in e['note'].lower():
                continue
            cand = []
            for h in houses:
                dist, along = _edge_dist(p, h, e['face'])
                if dist is not None and abs(along - float(e['pos'])) < TOL and dist > 0:
                    cand.append((dist, h))
            if not cand:
                key = (p['code'], 'nohouse')
                if key not in seen:
                    seen.add(key)
                    out.append(Finding('R12', 'error', '%s: Minifix edge hole on %s at %g has no cam housing in line '
                                       'with it.' % (p['code'], e['face'], float(e['pos'])), p['code']))
                continue
            dist, h = min(cand, key=lambda c: c[0])
            r = h['d'] / 2.0
            depth = float(e['z'])
            sys_h = [b for b in SYSTEMS if abs(dist - b) <= TOL]
            sys_e = [b for b in SYSTEMS if b + r <= depth + TOL]
            bolt = max(sys_e) if sys_e else None
            key = (p['code'], e['face'], round(dist, 1), depth)
            if key in seen:
                continue
            if not sys_h:
                seen.add(key)
                out.append(Finding('R12', 'error', '%s: Minifix housing %.1f mm from %s is not a standard drilling '
                                   'distance (%s); no bolt puts its head in the cam.' %
                                   (p['code'], dist, e['face'], '/'.join('B%d' % b for b in SYSTEMS)), p['code']))
            elif bolt is None:
                seen.add(key)
                out.append(Finding('R12', 'error', '%s: Minifix edge hole on %s is %g mm deep, does not cross the '
                                   'Ø%g housing at %.1f mm (needs >= %.1f).' %
                                   (p['code'], e['face'], depth, h['d'], dist, dist + r), p['code']))
            elif bolt != sys_h[0]:
                seen.add(key)
                out.append(Finding('R12', 'error', '%s: Minifix housing at %.1f mm from %s (B%d) but the edge hole is '
                                   'drilled %g mm deep for B%d bolts; the cam misses the bolt head and the joint never '
                                   'pulls tight.' % (p['code'], dist, e['face'], sys_h[0], depth, bolt), p['code']))
    return out
