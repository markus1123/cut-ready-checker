import math
from shapely.geometry import Polygon
from fc.core import Finding
from fc.gx.core import gx_rule

MIN_LEN = 50.0        # mm: shorter open bits are marks / lead-ins, not part outlines
MIN_AREA = 2500.0     # mm2 (~50 x 50): what the contour would enclose if closed - a part, not lettering
MAX_GAP_FRAC = 0.4    # gap at most 40 % of the drawn length: the chain is most of an outline (a rectangle missing
                      # its longest side still qualifies); a wider gap is an arc / single line, not a broken loop
MAX_OPEN = 2          # files with more open cut chains are drawn for open-vector cutting (operator runs each line)
BRIDGE_ANG = 179.0    # deg: both ends in line with the gap = a deliberate holding bridge left in a straight edge
BRIDGE_MAX = 25.0     # mm: holding bridges / tabs are short


def _end_angle(line, at_start):
    """Angle at an open end between the contour running away from it and the straight line across the gap.
    180 = the gap continues the contour straight on (a bridge left in a straight edge); ~90 = a corner."""
    L = line.length
    d = min(5.0, L / 10)
    a, b = (line.coords[0], line.coords[-1]) if at_start else (line.coords[-1], line.coords[0])
    q = line.interpolate(d if at_start else L - d)
    v1 = (q.x - a[0], q.y - a[1]); v2 = (b[0] - a[0], b[1] - a[1])
    n = math.hypot(*v1) * math.hypot(*v2)
    if n == 0:
        return 180.0
    return math.degrees(math.acos(max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / n))))


@gx_rule('GC02', 'Part outline left open: a whole side of the contour is missing')
def check(g):
    """A part is only cut free if its profile is a closed contour: CAM (VCarve, Fusion, SheetCAM) only offsets
    closed vectors to the outside / inside for a profile cut; an open vector is cut on-line or rejected, so the
    part stays joined to the sheet along the missing side, or the tool runs down the middle of the line and the part
    comes out a cutter-radius too small. G01 catches the near-miss join (< 2 mm). This rule catches the contour
    that is most of a part outline (encloses >= 2500 mm2 if closed, gap <= 40 % of its length) with a 2 mm+ gap:
    a whole edge (or arc chord) lost in export.
    Not flagged:
      * a short gap whose both ends run straight on into it (>= 179 deg): a holding bridge deliberately left in a
        straight edge (Opendesk sheets carry these and have been built many times);
      * files with more than two such open chains: drawn for open-vector cutting by an operator (AtFAB 'one to
        several' table), where every line is set up by hand - not an export failure of one part."""
    chains = [(l, layer) for l, layer in g.open_chains if l.length > MIN_LEN]
    if not chains or len(chains) > MAX_OPEN:
        return
    for line, layer in chains:
        a, b = line.coords[0], line.coords[-1]
        gap, L = math.dist(a, b), line.length
        if gap < 2.0 or gap > MAX_GAP_FRAC * L:
            continue
        P = Polygon(list(line.coords))
        if P.is_empty or not P.is_valid or P.area < MIN_AREA:
            continue
        if gap <= BRIDGE_MAX and min(_end_angle(line, True), _end_angle(line, False)) >= BRIDGE_ANG:
            continue
        c = P.centroid
        yield Finding('GC02', 'error',
                      'contour on %s is %.0f mm long but open: its ends are %.1f mm apart, so a whole side of a '
                      '%.0f cm2 part is not drawn - CAM cannot cut it free' % (layer, L, gap, P.area / 100),
                      (round(c.x / 10), round(c.y / 10)))
