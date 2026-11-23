from fc.core import Finding
from fc.gx.core import gx_rule
from shapely.geometry import Point

MAX_OVERHANG = 2.0   # mm: drawing/snap slack; more than this beyond the sheet edge and the cutter misses material
MIN_PART = 2000.0    # mm2: smaller loops are labels / offcuts, not nested parts


@gx_rule('G12', 'Part nested across the edge of the stock sheet')
def check(g):
    """When the file draws the stock sheet, every part must lie inside it. A part straddling the sheet border is
    partly nested over air / spoilboard: the profile toolpath there cuts nothing, so the part comes off the machine
    with a missing or short edge (wrong size, joints that don't close), and the cutter runs through the sheet
    margin where the hold-down screws and clamps sit (ShopBot hold-down guide; Vectric nesting 'border gap').
    Parts lying wholly outside the drawn sheet are another sheet / a reference drawing and are left alone. A part
    edge more than MAX_OVERHANG mm beyond the sheet edge cannot be explained by drawing precision."""
    sheet = g.sheet
    if sheet is None or sheet.is_empty:
        return
    border = sheet.exterior
    for p in g.parts:
        o = p.outer
        if o.is_empty or o.area < MIN_PART or o.within(sheet):
            continue
        inside = o.intersection(sheet).area
        if inside < 0.02 * o.area:
            continue                      # wholly outside: separate sheet or a reference view, not a mis-nest
        over = 0.0
        for x, y in o.exterior.coords:
            pt = Point(x, y)
            if not sheet.covers(pt):
                over = max(over, pt.distance(border))
        if over > MAX_OVERHANG:
            yield Finding('G12', 'error', 'part sticks %.0f mm over the edge of the stock sheet (%.0f%% of it '
                          'outside the material)' % (over, 100.0 * (1 - inside / o.area)), p.key)
