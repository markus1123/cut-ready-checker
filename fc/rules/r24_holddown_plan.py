"""Hold-down must be known before cutting. Source: ShopBot 'Holding Down Material for Cutting' p7-8
(docs/rules-from-manuals.md §5): onion skin 0.25-0.76 mm; vacuum alone does not hold small parts."""
from fc.core import rule, Finding
from fc import machine

KINDS = ('skruer', 'vakuum', 'onion', 'tabs')
SMALL_VAC = 50000.0   # mm^2: below this, vacuum alone is not trusted


@rule('R24', 'Hold-down method stated; onion skin 0.25-0.76 mm; small parts not on vacuum alone')
def check(d):
    V = d.P['verksted']
    h = V.get('holdning') or machine.HOLD.get('method')   # the workshop's own method if the design is silent
    if h is None:
        return [Finding('R24', 'warn', 'Hold-down method unknown (verksted.holdning: %s). Ask the workshop.' % '/'.join(KINDS))]
    if h not in KINDS:
        return [Finding('R24', 'error', 'Unknown hold-down %r.' % h)]
    out = []
    if h == 'onion':
        s = V.get('onion_skin')
        if s is None or not (0.25 <= s <= 0.76):
            out.append(Finding('R24', 'error', 'Onion skin %s mm; ShopBot recommends 0.25-0.76 mm.' % s))
    if h == 'vakuum':
        small = sorted({p['code'] for p in d.parts if p['L'] * p['B'] < SMALL_VAC})
        if small:
            out.append(Finding('R24', 'error', 'Vacuum only, but %s are under %.2f m2; add tabs or an onion skin.' % (', '.join(small), SMALL_VAC / 1e6)))
    return out
