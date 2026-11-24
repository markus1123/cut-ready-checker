from fc.core import Finding
from fc.gx.core import gx_rule

BIT = 3.175        # 1/8": the smallest router bit that cuts through furniture sheet
MIN_PART = 2500.0  # mm2: smaller loops are lettering / marks, not parts


@gx_rule('GC03', 'Part outline doubled: an opening hugs the outline so the part is a sliver no bit can cut')
def check(g):
    """A part is the sheet left between its outline and its openings. When an opening that covers most of the part
    runs so close to the outline that nowhere is the remaining material as wide as the smallest router bit (1/8" =
    3.175 mm), the two contours cannot be machined as drawn: the inside and outside toolpaths overlap, and what is
    left is a ring thinner than the bit that is thrown or destroyed. No real part is like that; it is a contour
    exported twice (stroke-to-path, offset copy, duplicated layer with a different tolerance), and CAM cuts both:
    the part comes out undersize and the sliver flies (SendCutSend / Ponoko: no double lines; VCarve 'find duplicate
    vectors'). Frames and rings with a real border keep at least a few bit widths of material; built designs in the
    corpus never come close to this."""
    for p in g.parts:
        o = p.outer
        if o.is_empty or o.area < MIN_PART or not p.inner:
            continue
        big = [i for i in p.inner if i.area > 0.5 * o.area and i.within(o.buffer(0.01))]
        if not big:
            continue
        i = max(big, key=lambda x: x.area)
        body = o.difference(i)
        if body.is_empty:
            continue
        if body.buffer(-BIT / 2).is_empty:
            yield Finding('GC03', 'error',
                          'an opening (%.0f%% of the part) runs within %.1f mm of the outline all round: the part is a '
                          'sliver thinner than the smallest bit (%.2f mm) - a contour exported twice; CAM cuts both and '
                          'the part comes out undersize' % (100 * i.area / o.area, BIT, BIT), p.key)
