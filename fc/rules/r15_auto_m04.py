"""Slide screws must stop inside the board they are driven into, never reach its opposite (finished) face."""
from fc.core import rule, Finding

MIN_WALL = 1.0   # mm of board that must remain between the screw tip and the opposite face
EPS = 0.05       # mm: float slack so exactly MIN_WALL passes


@rule('R15', 'Slide screws (length - slide metal thickness) leave >= 1 mm of board before the opposite face')
def check(d):
    """Workshop reason: a side-mount slide is screwed through its own steel flange into a carcass side, middle wall
    or drawer side. The part of the screw that enters the board is screw length minus the flange thickness. If that
    reaches (or comes within ~1 mm of) the board thickness, the screw tip lifts a bump in, or pokes straight out of,
    the opposite face, which is the finished outside of the carcass or the inside of the drawer. That cannot be
    repaired invisibly, so it stops the job: buy shorter screws (Hettich/Blum: 3.5x15/16 or 6.3x13 Euro for 16-19 mm).
    Checked from the slide spec (skrue_lengde - skinne_godstykkelse) against the measured thickness of every part that
    carries slide holes, and from each slide-pilot op's own screw_depth, so a wrong screw, a thinner board, or a
    thinner slide flange are all caught."""
    S = d.S
    spec_in = None
    if isinstance(S.get('skrue_lengde'), (int, float)):
        spec_in = S['skrue_lengde'] - (S.get('skinne_godstykkelse') or 0)
    out, seen = [], set()
    for p in d.parts:
        t = p['t']
        for o in p['ops']:
            if o['kind'] not in ('hole', 'through') or 'skinne' not in o.get('note', '').lower():
                continue
            depths = [x for x in (o.get('screw_depth'), spec_in) if isinstance(x, (int, float))]
            if not depths:
                continue
            dep = max(depths)
            wall = t - dep
            if wall < MIN_WALL - EPS and p['code'] not in seen:
                seen.add(p['code'])
                face = o.get('screw_face', o['face'])
                out.append(Finding('R15', 'error',
                                   '%s: %g mm slide screw through %.1f mm slide metal goes %.1f mm into %.1f mm '
                                   'board from %s, leaving %.1f mm (need >= %g): the tip marks or pierces the opposite '
                                   'face. Use screws <= %g mm.'
                                   % (p['code'], S.get('skrue_lengde', 0),
                                      S.get('skinne_godstykkelse', 0), dep, t, face, wall, MIN_WALL,
                                      int(t - MIN_WALL + (S.get('skinne_godstykkelse') or 0))), p['code']))
    return out
