"""Edges you can see from the front must be banded (raw chipboard edges swell and look unfinished)."""
from fc.core import rule, Finding
from fc.world import frames, neg, dot

VISIBLE = ('A', 'B', 'C', 'CH', 'D')


def band_edges(p):
    s = ' '.join(p.get('bands', []))
    if 'alle 4' in s:
        return {'x0', 'xL', 'y0', 'yB'}
    return {k for k, pat in (('x0', 'x=0'), ('xL', 'x=L'), ('y0', 'y=0'), ('yB', 'y=B')) if pat in s}


@rule('R06', 'Front-facing edges of carcass parts and all front edges are edge-banded, on the edge that really faces front')
def check(d):
    out = []
    for f in frames(d):
        p = f['part']
        if f['code'] == 'K':
            if band_edges(p) != {'x0', 'xL', 'y0', 'yB'}:
                out.append(Finding('R06', 'error', 'Fronts (K) must be banded on all 4 edges.', 'K'))
            continue
        if f['code'] not in VISIBLE:
            continue
        outward = {'x0': neg(f['ex']), 'xL': f['ex'], 'y0': neg(f['ey']), 'yB': f['ey']}
        front = [e for e, v in outward.items() if dot(v, (0, -1, 0)) > 0.99]
        for e in front:
            if e not in band_edges(p):
                out.append(Finding('R06', 'error', '%s (%s): the edge facing the front (%s) is not banded; bands are on %s.'
                                   % (p['code'], f['label'], e, sorted(band_edges(p)) or 'none'), p['code']))
    return [o for i, o in enumerate(out) if o.msg not in {x.msg for x in out[:i]}]
