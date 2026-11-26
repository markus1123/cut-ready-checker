from fc.gx import limits
from fc.core import Finding
from fc.gx.core import gx_rule
from shapely.strtree import STRtree

MIN_GAP = limits.FINEST       # mm: 1/16" - the finest end mill made for routing sheet at all; furniture uses 3.175-12 mm
TOUCH = 0.3         # mm: closer than this the outlines share one cut line (common-line nesting, snap tolerance)
SNAP = 0.5          # mm: ... and up to this on furniture-sized drawings (largest part >= 300 mm), as in G02
SNAP_L = 300.0      # mm
MIN_PART = 2500.0   # mm2 (~50 x 50 mm): smaller loops are lettering / decoration / offcuts, not nested parts
MIN_ROUTER_SLOT = 3.0   # mm: a through-opening narrower than this cannot be routed (1/8" bit) - a laser file
MAX_TIGHT_PAIRS = 2     # more sub-cutter pairs than this = the whole layout is deliberately tight (laser nest)


def _narrowest_opening(g, limit):
    """True if some through-opening is narrower than `limit` mm (no router bit fits inside it)."""
    for p in g.parts:
        for o in p.inner:
            try:
                if o.area > 1.0 and o.buffer(-limit / 2.0).is_empty:
                    return True
            except Exception:
                continue
    return False


@gx_rule('G10', 'Neighbouring parts nested closer than any router bit is wide')
def check(g):
    """A profile cut removes a kerf one bit-diameter wide, on a toolpath half a bit outside each part (tool
    compensation). Two parts nested side by side therefore need at least one bit diameter of sheet between their
    outlines, or the toolpath around one part runs through the edge of its neighbour, and the strip of sheet that
    should hold both parts down vanishes so they shift or are thrown. Furniture sheet (9-25 mm ply/MDF) is cut
    with 1/8" (3.175 mm) bits at the very smallest and normally 6-12 mm; the finest end mill that routes sheet at
    all is 1/16" (1.6 mm). A gap under 1.6 mm cannot be cut by any router bit. CAM nesting (Vectric "part gap",
    Opendesk making guide) sets the gap >= tool diameter for this reason; built designs in the corpus keep 2.5 mm+.
    Not flagged:
      * outlines that touch (< 0.3 mm): common-line nesting, one cut separates both parts; overlaps are G02's job;
      * tiny loops (< ~50 x 50 mm): lettering / decoration rather than nested parts;
      * drawings made for a kerf-thin process: if through-openings narrower than a 1/8" bit exist, the file is a
        laser/waterjet file (no router could cut those either), and if many part pairs sit at the same sub-cutter
        spacing the layout is a deliberate laser nest / unnested parts sheet that router CAM re-nests anyway.
        The router fault is one part dragged too close in an otherwise properly spaced nest.
    Narrowed after reading real files from other designers:
      * on furniture-sized drawings (largest part >= 300 mm) outlines up to 0.5 mm apart were drawn touching
        (common-line nesting) with snap imprecision - the same tolerance G02 gives overlaps; one cut separates them;
      * unitless drawings whose biggest part is under 300 mm (g.scale_uncertain: a 1:10 or cm drawing, or a model)
        give no reliable mm gap: a "1.4 mm" gap may be 14 mm on the real sheet."""
    if g.scale_uncertain:
        return
    parts = [p for p in g.parts if p.outer is not None and not p.outer.is_empty and p.outer.is_valid
             and p.outer.area >= MIN_PART]
    if len(parts) < 2:
        return
    outs = [p.outer for p in parts]
    L = max(max(o.bounds[2] - o.bounds[0], o.bounds[3] - o.bounds[1]) for o in outs)
    touch = SNAP if L >= SNAP_L else TOUCH
    tree = STRtree(outs)
    tight = []
    for i, a in enumerate(outs):
        for j in tree.query(a.buffer(MIN_GAP)):
            j = int(j)
            if j <= i:
                continue
            b = outs[j]
            if a.intersects(b):
                continue
            d = a.distance(b)
            if d == d and touch < d < MIN_GAP:
                tight.append((d, i, j))
    if not tight or len(tight) > MAX_TIGHT_PAIRS:
        return
    if _narrowest_opening(g, MIN_ROUTER_SLOT):
        return
    flagged = set()
    for d, i, j in sorted(tight):
        small = parts[i] if outs[i].area <= outs[j].area else parts[j]
        if small.key in flagged:
            continue
        flagged.add(small.key)
        yield Finding('G10', 'error',
                      'part is nested only %.1f mm from its neighbour (need >= one cutter width; even a 1/16" bit is '
                      '%.1f mm): the toolpath around one part cuts into the other' % (d, MIN_GAP), small.key)
