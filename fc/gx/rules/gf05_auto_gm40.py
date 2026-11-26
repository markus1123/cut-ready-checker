import re
from fc.core import Finding
from fc.gx.core import gx_rule

MIN_AREA = 10000.0   # mm2: a free-standing loop this big, or one with openings, is a real part - not a loose cut-out
INSIDE = re.compile(r'(?i)INSIDE')
OUTSIDE = re.compile(r'(?i)OUTSIDE')


@gx_rule('GF05', 'Part outline on the inside-profile layer (cutter offset into the part)')
def check(g):
    """Layer-driven CAM (Opendesk TOP-CUT-OUTSIDE / TOP-CUT-INSIDE, Vectric toolpath templates per layer) takes the
    side of the cutter from the layer: profiles of parts are cut OUTSIDE the line, openings INSIDE it. A part
    outline put on the inside-profile layer is cut with the tool inside the line, so the whole part comes out one
    bit diameter (6-12 mm) undersize - every tab, slot position and edge distance on it is wrong and it does not fit
    its neighbours. Flagged only when the file uses outside-profile layers for its other parts (so the convention
    is in use) and the loop is a real free-standing part: it has openings of its own or is >= 10000 mm2, and does
    not lie inside another part. Built Opendesk files do have small loose loops on the inside layer (cut-outs whose
    host the drawing does not close), never a panel."""
    if not any(OUTSIDE.search(p.layer or '') for p in g.parts):
        return
    for p in g.parts:
        if not INSIDE.search(p.layer or '') or OUTSIDE.search(p.layer or ''):
            continue
        if p.outer.area < MIN_AREA and not [i for i in p.inner if i.area > 20]:
            continue
        host = [q for q in g.parts if q is not p and q.outer.area > p.outer.area and q.outer.intersects(p.outer)
                and q.outer.intersection(p.outer).area > 0.5 * p.outer.area]
        if host:
            continue
        yield Finding('GF05', 'error',
                      'part outline (%.0f mm2) is on the inside-profile layer %s while the other parts are on an '
                      'outside-profile layer: CAM cuts it with the tool inside the line, one bit diameter undersize'
                      % (p.outer.area, p.layer), p.key)
