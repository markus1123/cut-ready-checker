"""Feed rates within the bit maker's chipload table. Too fast for the bit diameter snaps 1/8" bits or burns/chips melamine.
Source: Amana 'Solid Carbide Compression Spirals' v12, 2-flute, MDF/laminate at 18,000 rpm, depth of cut 1xD;
deeper passes: 2xD -25 %, 3xD -50 % (docs/rules-from-manuals.md §5)."""
from fc.core import rule, Finding
import nestlib

AMANA = {3.175: 2030.0, 6.35: 5590.0}   # mm/min at 1 x D


def limit(dia, doc):
    base = AMANA[min(AMANA, key=lambda k: abs(k - dia))]
    ratio = doc / dia
    if ratio <= 1.0:
        return base
    if ratio <= 2.0:
        return base * 0.75
    if ratio <= 3.0:
        return base * 0.5
    return 0.0


@rule('R21', 'Contour and groove feeds within Amana\'s chipload table for the bit and depth per pass')
def check(d):
    V, M = d.P['verksted'], d.P['maskintid']
    small, big = V['fres_liten_d'], V['fres_stor_d']
    out = []
    tmax = max(p['t'] for p in d.parts)
    doc = (tmax + 0.3) / M['omganger_kontur']
    lim = limit(big, doc)
    if M['mating_kontur'] > lim:
        out.append(Finding('R21', 'error', 'Contour feed %g mm/min at %.1f mm per pass with the Ø%g bit; Amana allows %.0f.'
                           % (M['mating_kontur'], doc, big, lim)))
    widths = set()
    for p in d.parts:
        for o in nestlib.classify(p, []):
            if o[0] == 'GROOVE':
                widths.add((round(o[2] - o[1], 2), o[3]))
    for w, depth in sorted(widths):
        bit = big if w >= big - 0.01 else small
        doc = depth / M['omganger_not']
        lim = limit(bit, doc)
        if M['mating_not'] > lim:
            out.append(Finding('R21', 'error', 'Groove %g wide is cut with the Ø%g bit at %g mm/min (%.1f mm per pass); Amana allows %.0f.'
                               % (w, bit, M['mating_not'], doc, lim)))
            break
    return out
