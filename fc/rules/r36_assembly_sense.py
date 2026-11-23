"""The assembled chest must make physical sense.

R36 top covers the carcass: the top's footprint contains every carcass panel (sides, bottom, middle wall).
R37 stands on its feet: nothing reaches lower than 5 mm above the underside of the legs (floor clearance), or the
    chest rocks on that part instead of standing on its legs.
R38 pilot holes: a screw pilot is smaller than the screw (Hettich slide screws Ø4) and at least half its diameter;
    a pilot as wide as the screw leaves nothing for the thread.
R39 bit lengths: a planned flute length longer than any real compression bit of that diameter is a typo
    (usually the overall length), and the reach rule would trust it.
"""
from fc.core import rule, Finding

CARCASS = ('C', 'CH', 'B', 'D')
FLOOR_GAP = 5.0
LONGEST = {3.175: 22.2, 6.35: 28.6}   # longest catalogued compression flute per diameter (Amana), mm


@rule('R36', 'The top covers the whole carcass footprint')
def top_covers(d):
    A = [a for a in d.asm if a['code'] == 'A']
    if not A:
        return []
    x, y, z, dx, dy, dz = A[0]['b']
    out = []
    for a in d.asm:
        if a['code'] not in CARCASS:
            continue
        bx, by, bz, bdx, bdy, bdz = a['b']
        if bx < x - 0.5 or bx + bdx > x + dx + 0.5 or by < y - 0.5 or by + bdy > y + dy + 0.5:
            out.append(Finding('R36', 'error', 'The top (%.0f..%.0f deep) does not cover %s (%.0f..%.0f); the carcass edge is exposed.'
                               % (y, y + dy, a['label'], by, by + bdy), 'A'))
            break
    return out


@rule('R37', 'Nothing hangs within 5 mm of the floor: the chest stands on its legs')
def stands(d):
    legs = [a for a in d.asm if a['code'] == 'BEIN']
    if not legs:
        return []
    floor = min(a['b'][2] for a in legs)
    low = [a for a in d.asm if a['code'] != 'BEIN' and a['b'][2] < floor + FLOOR_GAP]
    if low:
        a = min(low, key=lambda a: a['b'][2])
        gap = a['b'][2] - floor
        where = '%.0f mm below the feet' % -gap if gap < 0 else 'only %.0f mm above the floor' % gap
        return [Finding('R37', 'error', '%s reaches %s; the chest stands on it, not on its legs.' % (a['label'], where), a['code'])]
    return []


@rule('R38', 'Slide screw pilots are between half and 90 % of the screw diameter')
def pilots(d):
    S = d.S
    screw = S.get('skrue_d', 4.0)
    p = S.get('pilot_d')
    if p is None:
        return []
    if not (0.5 * screw <= p <= 0.9 * screw):
        return [Finding('R38', 'error', 'Slide pilot Ø%g for Ø%g screws (want %.1f..%.1f); the screw %s.'
                        % (p, screw, 0.5 * screw, 0.9 * screw, 'will not hold' if p > screw * 0.9 else 'will split the board'))]
    return []


@rule('R39', 'Planned flute lengths are not longer than any real compression bit of that diameter')
def flute_sane(d):
    V = d.P['verksted']
    out = []
    for dk, fk in (('fres_liten_d', 'fres_liten_skjaerlengde'), ('fres_stor_d', 'fres_stor_skjaerlengde')):
        dia, fl = V[dk], V.get(fk)
        mx = LONGEST.get(min(LONGEST, key=lambda k: abs(k - dia)))
        if fl is not None and fl > mx + 1:
            out.append(Finding('R39', 'error', 'Ø%g bit planned with a %g mm flute; no compression bit of that size cuts deeper than %g mm (overall length typed?).'
                               % (dia, fl, mx)))
    return out
