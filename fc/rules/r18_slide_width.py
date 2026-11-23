"""Hettich mounting sheet MS 10547 (KA 4532): max drawer width 550 mm (recommendation). Wider boxes on light
side-mount slides rack (one side leads), tilt and wear the slides. Source: docs/rules-from-manuals.md."""
from fc.core import rule, Finding


@rule('R18', 'Drawer box width within the slide maker\'s maximum (KA 4532: 550 mm)')
def check(d):
    mx = d.S.get('maks_skuffebredde', 550)
    bw = d.by['E1']['L'] + d.by['S']['t'] + d.by.get('SH', d.by['S'])['t']
    if bw > mx:
        return [Finding('R18', 'warn', 'Drawer box %.0f mm wide; Hettich recommends max %g mm for this slide. '
                        'Use 3 columns or a heavier slide.' % (bw, mx))]
    return []
