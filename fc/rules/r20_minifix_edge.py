"""The Minifix edge bore must reach the housing so the bolt head can enter the cam, but not run far past it.
Source: Häfele TCH 2023 cat. p 7.13/7.18: housing centre B = 24 or 34 mm from the edge, Ø15 housing
(docs/rules-from-manuals.md §2). Häfele gives no edge-bore depth, so the limits are geometric:
at least B (bolt head at the cam centre), at most B + housing radius + 3 mm."""
from fc.core import rule, Finding


@rule('R20', 'Minifix edge bore reaches the housing centre and stops within 3 mm past the housing')
def check(d):
    K = d.P['korpus']
    B, r = K['minifix_hus_avstand'], K['minifix_hus_d'] / 2
    if B not in (24, 34):
        return [Finding('R20', 'error', 'Minifix housing distance B = %g; Häfele bolts exist for B24 and B34 only.' % B)]
    out, seen = [], set()
    for p in d.parts:
        for o in p['ops']:
            if o['kind'] != 'edge' or not o['note'].startswith('Minifix-bolt'):
                continue
            z = o['z']
            if (z < B or z > B + r + 3) and (p['code'], z) not in seen:
                seen.add((p['code'], z))
                out.append(Finding('R20', 'error', '%s: Minifix edge bore %g deep, housing centre at B%g: needs %g..%g.'
                                   % (p['code'], z, B, B, B + r + 3), p['code']))
    return out
