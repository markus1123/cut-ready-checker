"""Screw lengths that actually hold."""
from fc.core import rule, Finding


@rule('R09', 'Handle screws reach >= 5 mm into the handle thread and do not bottom out')
def check(d):
    F = d.P['front']
    hs = F.get('handtak_skrue_lengde', 40)
    stack = d.by['K']['t'] + d.by['E1']['t']
    eng = hs - stack
    if eng < 5:
        return [Finding('R09', 'error', 'Handle screw M4x%g through %.1f mm (front + drawer end) leaves %.1f mm in the handle (need >= 5). '
                        'Buy M4x%d.' % (hs, stack, eng, 5 * round((stack + 7) / 5)), 'K')]
    if eng > 12:
        return [Finding('R09', 'error', 'Handle screw M4x%g bottoms out in the handle (%.1f mm past the front).' % (hs, eng), 'K')]
    return []
