"""The flute lengths the generator plans with must be those of a real bit. Source: Amana part names / retailer specs
(docs/rules-from-manuals.md §5): 1/8" compression 20.6 (46180, 2 fl) or 9.5 (46137/46139, 1 fl); 1/4" compression 22.2 (46170)."""
from fc.core import rule, Finding

KNOWN = {3.175: (9.5, 20.6), 6.35: (22.2,)}


@rule('R26', 'Planned flute lengths match a real compression bit (Amana 1/8": 9.5 or 20.6; 1/4": 22.2)')
def check(d):
    V = d.P['verksted']
    out = []
    for dk, fk in (('fres_liten_d', 'fres_liten_skjaerlengde'), ('fres_stor_d', 'fres_stor_skjaerlengde')):
        dia, fl = V[dk], V.get(fk)
        known = KNOWN.get(min(KNOWN, key=lambda k: abs(k - dia)), ())
        if fl is not None and not any(abs(fl - k) < 0.3 for k in known) and not V.get(fk + '_malt'):
            out.append(Finding('R26', 'warn', 'Ø%g bit planned with %g mm flute; known bits have %s. Measure the workshop\'s bit and set %s_malt=true.'
                               % (dia, fl, ' or '.join('%g' % k for k in known), fk)))
    return out
