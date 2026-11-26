from collections import Counter
from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx.rules.g06_auto_gm01 import _axes

SAME_W = 0.3          # mm: slots this close in width take the same mating sheet
SHORT = (0.55, 0.85)  # a lone slot this fraction of a repeated length: shortened by an edit, not a different joint
MIN_SET = 3           # identical slots that make an array; with only two the odd one may be a deliberately different joint
TAB_TOL = 0.6         # mm: a tab edge this close to a slot's length fits it (slots are drawn tab + 0-0.5 mm)
import math


def _tabs(g, w):
    """Tip widths of the tabs on all part outlines that fit a w-wide slot: an outline edge whose two neighbouring
    edges turn ~90 degrees and are 0.6-3 x w long (a tab sticks out about one sheet thickness = the slot width)."""
    out = []
    for p in g.parts:
        c = list(p.outer.exterior.coords)[:-1]
        n = len(c)
        if n < 4: continue
        for k in range(n):
            a0, a, b, b0 = c[k - 1], c[k], c[(k + 1) % n], c[(k + 2) % n]
            L, s1, s2 = math.dist(a, b), math.dist(a0, a), math.dist(b, b0)
            if not L or not (0.6 * w <= s1 <= 3 * w and 0.6 * w <= s2 <= 3 * w): continue
            cos = lambda u, v: abs(u[0] * v[0] + u[1] * v[1]) / (math.hypot(*u) * math.hypot(*v))
            e = (b[0] - a[0], b[1] - a[1])
            if cos(e, (a[0] - a0[0], a[1] - a0[1])) < 0.17 and cos(e, (b0[0] - b[0], b0[1] - b[1])) < 0.17:
                out.append(L)
    return out


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
    repeated families; built designs never show a lone short copy.
    Narrowed after reading real files from other designers:
      * a lone short slot whose length matches the tip of a tab on some part outline (within 0.6 mm; a tab is an
        edge between two square turns about one slot width long) has its own mating part - it is a different joint (a rail, a back, a smaller
        shelf), not an arrayed slot shortened by an edit; the shortened copy has no tab of its new length."""
    S = _slots(g)
    done = set()
    for w, L, p in S:
        fam = Counter(round(L2) for w2, L2, _ in S if abs(w2 - w) <= SAME_W)
        if fam[round(L)] != 1:
            continue
        for Lc, n in fam.items():
            if n >= MIN_SET and SHORT[0] * Lc <= L <= SHORT[1] * Lc and p.key not in done:
                if any(abs(e - L) <= TAB_TOL for e in _tabs(g, w)):
                    break
                done.add(p.key)
                yield Finding('GF10', 'error',
                              'slot %.1f x %.0f mm is %.0f %% shorter than the %d identical %.1f x %.0f mm slots of '
                              'this file: the mating part will not pass through' % (w, L, 100 * (1 - L / Lc), n, w, Lc),
                              p.key)
                break
