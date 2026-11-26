from collections import Counter
from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx.rules.g06_auto_gm01 import _axes

SAME_W = 0.3          # mm: slots this close in width take the same mating sheet
SHORT = (0.55, 0.85)  # a lone slot this fraction of a repeated length: shortened by an edit, not a different joint
MIN_SET = 3           # identical slots that make an array; with only two the odd one may be a deliberately different joint


def _slots(g):
    out = []
    for p in g.parts:
        for i in p.inner:
            if i.area < 50:
                continue
            ax = _axes(i)
            if not ax:
                continue
            r, w, L = ax
            if 3 <= w <= 40 and L >= 1.5 * w and i.area > 0.8 * r.area:
                out.append((w, L, p))
    return out


@gx_rule('GF10', 'One slot of a set of identical slots drawn markedly shorter')
def check(g):
    """Slots receive a mating part of fixed width: slot length = mating width + clearance (Opendesk / WikiHouse
    slot-joint guidance). When a design repeats a slot (same width, same length, three or more times - an array) and ONE slot of
    that width is 15-45 % shorter than the repeated length - with no other slot sharing its length - it was
    shortened by an edit (stretch / trim of one copy of an arrayed feature): the mating part does not pass through
    and the joint cannot be assembled without recutting. Slots of genuinely different joints come as their own
    repeated families; built designs never show a lone short copy."""
    S = _slots(g)
    done = set()
    for w, L, p in S:
        fam = Counter(round(L2) for w2, L2, _ in S if abs(w2 - w) <= SAME_W)
        if fam[round(L)] != 1:
            continue
        for Lc, n in fam.items():
            if n >= MIN_SET and SHORT[0] * Lc <= L <= SHORT[1] * Lc and p.key not in done:
                done.add(p.key)
                yield Finding('GF10', 'error',
                              'slot %.1f x %.0f mm is %.0f %% shorter than the %d identical %.1f x %.0f mm slots of '
                              'this file: the mating part will not pass through' % (w, L, 100 * (1 - L / Lc), n, w, Lc),
                              p.key)
                break
