"""Follow every connector hole across its joint in 3D. A Minifix bolt hole in the top must meet the edge
hole in the side; dowel meets dowel; confirmat meets its pilot. Also: handed parts (left/right mirror)."""
from fc.core import rule, Finding
from fc.world import frames, holes, inside, proper, add, mul, neg, dot

CONNECT = ('Minifix-bolt', 'Plugg', 'Konfirmat', 'Skrue til list', 'Forbor skrue')
TOL = 0.6


def is_connector(o):
    return any(o['note'].startswith(c) for c in CONNECT)


@rule('R03', 'Joint continuity in 3D: every connector hole has a coaxial partner hole in the part it touches')
def continuity(d):
    inst = frames(d)
    allh = [(f, h) for f in inst for h in holes(f)]
    out, seen = [], set()
    for f, h in allh:
        if not is_connector(h['op']):
            continue
        probe = add(h['entry'], mul(h['dir'], -0.5))          # just outside the part, where the mate must be
        mates = [g for g in inst if g is not f and inside(g['box'], probe)]
        if not mates:
            if h['op']['kind'] == 'through':
                continue                                       # screw-head end of a through hole: open is fine
            key = (f['code'], h['op']['note'], 'air')
            if key not in seen:
                seen.add(key)
                out.append(Finding('R03', 'error', '%s (%s): %s hole Ø%g opens into nothing.' % (f['code'], f['label'], h['op']['note'], h['d']), f['code']))
            continue
        g = mates[0]
        ok = False
        for gh in holes(g):
            if dot(gh['dir'], h['dir']) < -0.99:
                dv = [a - b for a, b in zip(gh['entry'], h['entry'])]
                if sum(v * v for v in dv) ** 0.5 < TOL:
                    ok = True; break
        if not ok:
            key = (f['code'], g['code'], h['op']['note'])
            if key not in seen:
                seen.add(key)
                out.append(Finding('R03', 'error', '%s -> %s: %s hole Ø%g at part (%s) has no matching hole in %s (%s).'
                                   % (f['code'], g['code'], h['op']['note'], h['d'],
                                      ', '.join('%g' % h['op'].get(k, h['op'].get('pos', 0)) for k in ('x', 'y') if k in h['op']) or h['op']['face'],
                                      g['code'], g['label']), f['code']))
    return out


def _band_edges(p):
    s = ' '.join(p.get('bands', []))
    if 'alle 4' in s:
        return {'x0', 'xL', 'y0', 'yB'}
    return {k for k, pat in (('x0', 'x=0'), ('xL', 'x=L'), ('y0', 'y=0'), ('yB', 'y=B')) if pat in s}


def signature(p, mirror):
    """Op set of a part, optionally mirrored in x ('x') or y ('y'), for symmetry tests."""
    L, B = p['L'], p['B']
    sig = set()
    for o in p['ops']:
        k = o['kind']
        if k == 'manual':
            continue
        if k == 'groove':
            y1, y2 = o['y1'], o['y2']
            if mirror == 'y':
                y1, y2 = B - y2, B - y1
            sig.add(('g', o['face'], round(y1, 1), round(y2, 1), o['z'])); continue
        if k == 'edge':
            e, pos = o['face'], float(o['pos'])
            if mirror == 'x':
                e = {'kant:venstre ende': 'kant:høyre ende', 'kant:høyre ende': 'kant:venstre ende'}.get(e, e)
                if e.endswith('kant'): pos = L - pos
            if mirror == 'y':
                e = {'kant:overkant': 'kant:underkant', 'kant:underkant': 'kant:overkant'}.get(e, e)
                if e.endswith('ende'): pos = B - pos
            sig.add(('e', e, round(pos, 1), o['d'], str(o['z']))); continue
        x, y = o['x'], o['y']
        if mirror == 'x': x = L - x
        if mirror == 'y': y = B - y
        sig.add(('h', k, o['face'], round(x, 1), round(y, 1), o['d'], str(o['z'])))
    bands = _band_edges(p)
    if mirror == 'x':
        bands = {{'x0': 'xL', 'xL': 'x0'}.get(b, b) for b in bands}
    if mirror == 'y':
        bands = {{'y0': 'yB', 'yB': 'y0'}.get(b, b) for b in bands}
    sig.add(('bands',) + tuple(sorted(bands)))
    return sig


@rule('R04', 'Handedness: a part used as a mirror image (left vs right) must be symmetric, or be cut as a mirrored copy')
def handed(d):
    out, seen = [], set()
    for f in frames(d):
        if proper(f) or f['code'] in seen:
            continue
        p = f['part']
        base = signature(p, None)
        if base == signature(p, 'x') or base == signature(p, 'y'):
            continue
        seen.add(f['code'])
        diff = sorted(base - signature(p, 'x'), key=str)[:2]
        out.append(Finding('R04', 'error', '%s (%s) is installed as the MIRROR image of the part as cut, and its holes/bands '
                           'are not symmetric (e.g. %s). Holes end up front<->back. Cut a mirrored left/right version.'
                           % (p['code'], f['label'], diff), p['code']))
    return out
