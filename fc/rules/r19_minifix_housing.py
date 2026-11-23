"""Häfele Minifix 15 housing depth must match the board it is drilled into.
Source: Häfele TCH 2023 cat. p 7.13 (docs/rules-from-manuals.md §2). Too shallow: the cam sits proud and the
bolt head misses the cam's ramp. Too deep: thin skin under the housing on the visible face."""
from fc.core import rule, Finding

# nominal board thickness -> (housing depth, + tolerance)  262.26.033 / .034 / .035
HAFELE = {16: (12.5, 0.5), 18: (13.5, 0.5), 19: (14.0, 0.5)}


@rule('R19', 'Minifix housing depth matches the Häfele table for the board thickness (16/18/19 mm -> 12.5/13.5/14.0 +0.5)')
def check(d):
    out, seen = [], set()
    for p in d.parts:
        for o in p['ops']:
            if not o['note'].startswith('Minifix-hus'):
                continue
            nom = min(HAFELE, key=lambda t: abs(t - p['t']))
            want, tol = HAFELE[nom]
            if abs(nom - p['t']) > 1.0:
                key = (p['code'], 'thk')
                if key not in seen:
                    seen.add(key)
                    out.append(Finding('R19', 'warn', '%s: %.1f mm board has no Minifix 15 housing in the Häfele table.' % (p['code'], p['t']), p['code']))
                continue
            if not (want - 0.01 <= o['z'] <= want + tol + 0.01) and (p['code'], o['z']) not in seen:
                seen.add((p['code'], o['z']))
                out.append(Finding('R19', 'error', '%s: Minifix housing %.1f deep in %g mm board; Häfele wants %.1f (+%.1f) for this board.'
                                   % (p['code'], o['z'], nom, want, tol), p['code']))
    return out
