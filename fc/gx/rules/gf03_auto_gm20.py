from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx.rules.g06_auto_gm01 import _slot_width, ply_tol

LOOSE = 2.0      # mm over nominal: thickest in-tolerance ply (t + 0.2 + 0.03t) plus a generous 1 mm fit clearance
OTHER = 3.6      # mm over nominal: wider than this the slot is evidently for another, thicker part, not this sheet
FIT_HI = 1.6     # mm over nominal: the loosest slot fit seen in built designs (press-fit 0-0.9, sliding 1.5)


@gx_rule('GF03', 'Slots too loose for the sheet: no slot in the file fits the stated thickness')
def check(g):
    """A slot joint holds only by its fit: Opendesk / WikiHouse / ShopBot press-fit slots are drawn at sheet
    thickness + 0-0.5 mm, built designs in the corpus at up to +1.5 mm (a sliding fit). Plywood is never thicker
    than nominal by more than its tolerance (EN 315: 0.2 + 0.03 t, 0.74 mm at 18 mm). When the file states the sheet
    thickness and NONE of its slots fits that sheet - every slot for a mating sheet is 2-3.6 mm oversize - the slots
    were drawn for thicker stock (21 mm for 18 mm ply) or got the fit clearance twice: every joint has 1.3+ mm of
    play, racks and falls apart under sideways load (glue or wedges cannot fill it). Slots more than 3.6 mm over
    are for another, thicker part and are left alone; any slot that does fit the sheet means the family is right.
    Only the slot core is measured (dog-bone corner lobes stripped). Needs a STATED thickness; guessing it from the
    slots would be circular."""
    th = g.thickness
    if not th or g.thickness_source is None or th < 3:
        return
    ws = []
    for p in g.parts:
        for i in p.inner:
            w = _slot_width(i)
            if w is not None and 0.9 * th <= w <= 1.5 * th:
                ws.append((w, p))
    if not ws:
        return
    if any(th - ply_tol(th) <= w <= th + FIT_HI for w, _ in ws):
        return
    done = set()
    for w, p in ws:
        if th + LOOSE < w <= th + OTHER and p.key not in done:
            done.add(p.key)
            yield Finding('GF03', 'error',
                          'slot %.1f mm wide for the stated %.1f mm sheet (%.1f mm oversize) and no slot in the file '
                          'fits that sheet: every joint has play, racks and comes apart' % (w, th, w - th), p.key)
