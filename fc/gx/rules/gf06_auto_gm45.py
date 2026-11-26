from fc.core import Finding
from fc.gx.core import gx_rule

ONION = 0.8   # mm: thickest onion skin ShopBot recommends is 0.030 in = 0.76 mm; more cannot be snapped or trimmed off


@gx_rule('GF06', 'Part profile cut stops short of the sheet: the part is not cut free')
def check(g):
    """A part is freed by its profile cut going through the sheet. Layer-driven CAM (Opendesk
    TOP-CUT-OUTSIDE_18.000MM, Vectric toolpath templates) takes the cut depth from the layer: when one part's
    profile depth is less than the sheet thickness by more than an onion skin (ShopBot: 0.25-0.76 mm, snapped or
    trimmed off after cutting), the part stays attached to the sheet by a skin it cannot be broken out of - it is torn
    out with ragged, splintered edges or has to be recut. Sheet thickness as stated (manifest / file name / deepest
    through-cut layer); built designs cut every part profile to that depth."""
    th = g.thickness
    if not th or th < 3:
        return
    for p in g.parts:
        if p.depth and p.depth < th - ONION:
            yield Finding('GF06', 'error',
                          'profile of this part cut %.1f mm deep in %.1f mm sheet: %.1f mm of skin left, more than an '
                          'onion skin (%.2f mm) - the part is not cut free' % (p.depth, th, th - p.depth, ONION), p.key)
