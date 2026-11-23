"""Slide screw holes must be where the slide maker's drawing puts them, not where someone measured by eye.
Source: Hettich MS 10547 p2 (KA 4532/400): cabinet member 37/165/229 from the cabinet front edge, drawer member
37/165/291 from the drawer front datum (docs/rules-from-manuals.md §1). Only checked for slide/length combos we have data for."""
from fc.core import rule, Finding

DATA = {('KA 4532', 400): dict(korpus=[37, 165, 229], skuff=[37, 165, 291])}
TOL = 0.5


@rule('R22', 'Verified slide hole pattern matches the manufacturer drawing (Hettich KA 4532/400)')
def check(d):
    S = d.S
    if not S.get('verifisert'):
        return []
    key = next((k for k in DATA if k[0] in S.get('modell', '') and k[1] == S.get('lengde')), None)
    if not key:
        return []
    out = []
    for side in ('korpus', 'skuff'):
        have = sorted(x for x, _ in S.get(side + '_hull', []))
        want = DATA[key][side]
        if len(have) != len(want) or any(abs(a - b) > TOL for a, b in zip(have, want)):
            out.append(Finding('R22', 'error', '%s holes for %s/%d at %s; Hettich drawing says %s.' % (side, key[0], key[1], have, want)))
    return out
