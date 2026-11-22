"""Fronts after edge banding: real gaps between fronts and to the carcass outline."""
from fc.core import rule, Finding

DEFAULT_BAND = 0.5   # iron-on melamine/ABS banding if nothing is specified


@rule('R08', 'Front gaps after edge banding >= 1.5 mm; fronts do not stick out past the carcass')
def check(d):
    F, P = d.P['front'], d.P
    k = d.by['K']
    band = F.get('kantlist_tykkelse', DEFAULT_BAND)
    out = []
    gap = F['fuge'] - 2 * band
    if gap < 1.5:
        out.append(Finding('R08', 'error', 'Gap between fronts %.1f mm after %.1f mm banding (need >= 1.5). Cut sizes must deduct the banding.'
                           % (gap, band), 'K'))
    cols, rows = P['kolonner'], P['rader']
    width = cols * k['L'] + (cols - 1) * F['fuge'] + 2 * band   # inner bands eat the gap, outer ones add width
    if width > d.info['W'] + 2.0:
        out.append(Finding('R08', 'error', 'Fronts span %.1f mm, carcass %.1f: fronts stick out %.1f mm each side.'
                           % (width, d.info['W'], (width - d.info['W']) / 2), 'K'))
    height = rows * k['B'] + (rows - 1) * F['fuge'] + 2 * band
    if height > d.info['HS'] + 2.0:
        out.append(Finding('R08', 'error', 'Fronts stack to %.1f mm on a %.1f mm high carcass.' % (height, d.info['HS']), 'K'))
    return out
