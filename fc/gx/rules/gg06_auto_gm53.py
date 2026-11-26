import math, re
from fc.gx import limits
from fc.core import Finding
from fc.gx.core import gx_rule

D_MIN = limits.BIT_MIN - 0.4   # 2.775 mm: what a 1/8" bit can still stand in for (same slack as GC06)
MIN_LEN = 8.0                  # mm: shorter = a mark, not a groove / housing
TOOL = re.compile(r'(\d+(?:\.\d+)?)\s*MM[ _-]*(?:CUTTER|BIT|TOOL|END ?MILL)')   # layer names its cutter
SHALLOW = 3.0                  # mm: engraving / logo depth - fine 1-2 mm cutters with short flutes do cut that deep


@gx_rule('GG06', 'Pocket / groove narrower than the smallest router bit')
def check(g):
    """A pocket is cleared by a round bit, so nowhere can it be narrower than the bit. The smallest bit used on
    furniture sheet is 1/8" (3.175 mm); pockets are normally cleared with 6 mm bits. A pocket loop that a 2.775 mm
    disc (1/8" less 0.4 mm slack) fits nowhere in, and that is at least 8 mm long, cannot be machined as drawn:
    CAM leaves it out (VCarve: tool too large for the vector) or a bigger bit cuts it oversize, and the back,
    panel or fitting it was drawn for does not fit. Round pocket features (blind drill holes, made with a drill, not
    a router) are not judged, nor are shallow pockets (<= 3 mm: engraved logos / marks, cut with fine 1-2 mm
    cutters - Opendesk files do this on TOP-POCKET-INSIDE_01MM / 2MM_POCKET_1MM_CUTTER layers), nor a strip that
    touches another pocket, an opening or the outline (one piece of a larger clearance), nor pockets on a layer that
    names its own fine cutter ('..._1MM_CUTTER')."""
    for p in g.parts:
        pk = [f for f in p.features if f.op == 'pocket' and f.geom is not None]
        for f in pk:
            if f.r or f.geom.geom_type != 'Polygon' or f.geom.area < 5:
                continue
            if f.depth is not None and f.depth <= SHALLOW:
                continue
            x = f.geom
            if any(h is not f and h.geom.distance(x) < 0.5 for h in pk):
                continue
            if p.outer.exterior.distance(x) < 0.5 or any(i.distance(x) < 0.5 for i in p.inner):
                continue          # a strip along an edge / opening: cleared together with the cut beside it
            m = TOOL.search(f.layer.upper())
            if m and float(m.group(1)) < D_MIN:
                continue          # the layer names its own fine cutter: the shop set this pocket up for it
            if not x.is_valid: continue
            if not x.buffer(-D_MIN / 2).is_empty: continue
            r = x.minimum_rotated_rectangle
            if r.geom_type != 'Polygon': continue
            cs = list(r.exterior.coords)
            a, b = math.dist(cs[0], cs[1]), math.dist(cs[1], cs[2])
            if max(a, b) < MIN_LEN: continue
            yield Finding('GG06', 'error', 'pocket %.1f x %.0f mm on %s: narrower than the smallest router bit '
                          '(1/8" = %.2f mm) - it cannot be machined as drawn' % (min(a, b), max(a, b), f.layer,
                                                                               limits.BIT_MIN), p.key)
            break
