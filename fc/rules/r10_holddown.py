"""Narrow parts shift during the last pass unless held by tabs/onion skin."""
from fc.core import rule, Finding


@rule('R10', 'Parts narrower than 60 mm (or smaller than 0.02 m2) need tabs, which the files do not have')
def check(d):
    out = []
    for p in d.parts:
        if min(p['L'], p['B']) < 60 or p['L'] * p['B'] < 20000:
            out.append(Finding('R10', 'error', '%s %gx%g is too small/narrow to stay put without tabs; add tabs or make it wider.'
                               % (p['code'], p['L'], p['B']), p['code']))
    return out
