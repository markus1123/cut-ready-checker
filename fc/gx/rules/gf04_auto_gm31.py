from fc.core import Finding
from fc.gx.core import gx_rule
from shapely.geometry import LineString, Point

MIN_PART = 2500.0    # mm2: smaller loops are lettering / marks, not parts
MIN_INSIDE = 40.0    # mm of the line inside the part: far more than a lead-in or a snapping overshoot
STRAIGHT = 0.5       # mm: a construction / centre line is straight; broken outline pieces are not
END_IN = 0.05        # mm: the line ends strictly inside the outline (a lead-in ends ON it)


@gx_rule('GF04', 'Straight open line on a cut layer runs from outside into a part and stops inside it')
def check(g):
    """Every vector on a through-cut layer is machined through the full sheet. A straight open line on such a
    layer that enters a part through its outline and ends inside the part - a construction, centre or
    reference line left on the cut layer, typically running from outside to the middle of a non-rectangular part -
    is cut as a full-depth slit 40+ mm into the part: the part is cracked open along it, weakened, or breaks there
    in use (SendCutSend: remove construction lines and anything that is not a cut path; Opendesk: only toolpath
    geometry on the CUT layers). Lead-ins and snapping overshoots stay within a few mm of the outline; curved or
    polyline pieces of a broken outline are left to the open-outline rules; lines lying wholly inside a part
    (marking lines) do not cut into it from the edge. Lines crossing a part edge to edge are another rule's case."""
    parts = [p for p in g.parts if p.outer.area >= MIN_PART and p.outer.is_valid]
    for line, layer in g.open_chains:
        if line.length < MIN_INSIDE or len(line.coords) < 2:
            continue
        a, b = Point(line.coords[0]), Point(line.coords[-1])
        ch = LineString([a, b])
        if ch.length < MIN_INSIDE or max(ch.distance(Point(c)) for c in line.coords) > STRAIGHT:
            continue
        for p in parts:
            o = p.outer
            if not line.intersects(o):
                continue
            x = line.intersection(o.exterior)
            n = 0 if x.is_empty else len(getattr(x, 'geoms', [x]))
            if n != 1:
                continue
            ends_in = [e for e in (a, b) if o.contains(e) and o.exterior.distance(e) > END_IN]
            if len(ends_in) != 1:
                continue
            inside = line.intersection(o).length
            if inside >= MIN_INSIDE:
                yield Finding('GF04', 'error',
                              'straight open line on cut layer %s runs %.0f mm from the part edge into the part and '
                              'stops inside it: it is cut as a full-depth slit (construction line left on the cut '
                              'layer?)' % (layer, inside), p.key)
