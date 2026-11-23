"""Slide screws: long enough to hold, short enough not to dimple the other face.
Source: Hettich MS 10547 p1 (KA 4532): Ø4 x 14 chipboard screws on cabinet and drawer side
(docs/rules-from-manuals.md §1). Screw in board = length - runner flange; must leave >= min_restvegg_blindhull."""
from fc.core import rule, Finding

MIN_BITE = 10.0


@rule('R25', 'Slide screws bite >= 10 mm and leave the blind-hole minimum wall in the thinnest board they go into')
def check(d):
    S, V = d.S, d.P['verksted']
    bite = S['skrue_lengde'] - S.get('skinne_godstykkelse', 0)
    wall = V.get('min_restvegg_blindhull', 2)
    out = []
    if bite < MIN_BITE:
        out.append(Finding('R25', 'error', 'Slide screw %g mm bites only %.1f mm; Hettich uses Ø4 x 14.' % (S['skrue_lengde'], bite)))
    for code in ('C', 'CH', 'D', 'S', 'SH'):
        p = d.by.get(code)
        if p and bite > p['t'] - wall:
            out.append(Finding('R25', 'error', 'Slide screw %g mm goes %.1f mm into the %.1f mm %s; leaves %.1f mm (need %g). Use Ø4 x 14.'
                               % (S['skrue_lengde'], bite, p['t'], code, p['t'] - bite, wall), code))
    return out
