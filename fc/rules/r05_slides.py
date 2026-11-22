"""Slides are bought parts with a fixed hole pattern. Every slide hole/mark must sit where the slide's holes are
(depth from the front, height from the slide centre line) on BOTH sides of every opening and every drawer box."""
from fc.core import rule, Finding
from fc.world import frames, holes

TOL = 0.3


@rule('R05', 'Slide holes on carcass walls and drawer sides match the slide pattern (depth from front, height), both sides')
def check(d):
    S, info = d.S, d.info
    out = []
    if S.get('verifisert') and S.get('korpus_hull'):
        cab = {round(x, 1) for x, _ in S['korpus_hull'] + (S.get('korpus_hull_alternativ') or [])}
        box = {round(x, 1) for x, _ in S.get('skuff_hull') or []} or {40.0, S['lengde'] - 40.0}
    else:
        cab = box = {40.0, float(S['lengde'] - 40)}
    rows_z = info['slide_zc']
    faces = {}
    for f in frames(d):
        if f['code'] not in ('C', 'CH', 'D', 'S', 'SH'):
            continue
        drawer = f['code'] in ('S', 'SH')
        for h in holes(f):
            if 'kinne' not in h['op']['note']:
                continue
            Yd, Zh = h['entry'][1], h['entry'][2]
            allowed = box if drawer else cab
            if not any(abs(Yd - a) < TOL for a in allowed):
                out.append(Finding('R05', 'error', '%s (%s): slide hole at %.1f mm from the front; the slide has holes at %s.'
                                   % (f['code'], f['label'], Yd, sorted(allowed)), f['code']))
            if not drawer and not any(abs(Zh - z) <= S['hoyde'] / 2 for z in rows_z):
                out.append(Finding('R05', 'error', '%s: slide hole at height %.1f is outside every slide row.' % (f['code'], Zh), f['code']))
            # which face of the opening is this? key by (plane X rounded, outward side)
            faces.setdefault((round(h['entry'][0], 1), drawer), []).append((Yd, Zh))
    # every opening wall face that should carry a slide has holes in every row
    T = info['T']; Wo = info['Wo']; cols = d.P['kolonner']
    for c in range(cols):
        xl = T + c * (Wo + T); xr = xl + Wo
        for X, name in ((xl, 'left wall'), (xr, 'right wall')):
            pts = faces.get((round(X, 1), False), [])
            for r, z in enumerate(rows_z):
                n = sum(1 for (_, Zh) in pts if abs(Zh - z) <= S['hoyde'] / 2)
                if n < 2:
                    out.append(Finding('R05', 'error', 'Column %d, row %d, %s: %d slide hole(s)/marks (need >= 2).' % (c + 1, r + 1, name, n)))
    return [o for i, o in enumerate(out) if o.msg not in {x.msg for x in out[:i]}][:12]
