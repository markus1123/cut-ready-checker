from fc.core import Finding
from fc.gx.core import gx_rule
from shapely.strtree import STRtree

SAME = 0.9        # area ratio: the two loops are the same opening drawn twice
OVER = 0.5        # they share at least half their area: one is a shifted copy of the other, not a neighbour
SHIFT = 0.3       # mm: below this the copies coincide and the cut is unchanged (just a double pass)


@gx_rule('GF02', 'Opening drawn twice, the copy shifted (duplicate geometry)')
def check(g):
    """Every closed loop on a through-cut layer is machined. When an opening (slot, mortise, cut-out) is drawn twice
    and the copy is shifted - a move / copy / offset left behind after an edit - CAM cuts both loops: the opening comes
    out wider by the shift (a press-fit slot 1.2 mm oversize rattles and racks), and the tool runs twice along almost
    the same edge, leaving a thin sliver that burns or breaks off (Vectric 'Delete duplicate vectors' clean-up step;
    SendCutSend / Ponoko file guides: no duplicate or overlapping lines). Found as two openings in one part with
    the same area (within 10 %) that overlap by more than half and whose centres are at least 0.3 mm apart.
    Built designs never have that: deliberately overlapping loops (dog-bone circles on a rectangle, a slot through
    a pocket) differ a lot in size."""
    for p in g.parts:
        ii = [i for i in p.inner if i.area >= 20 and i.is_valid]
        if len(ii) < 2:
            continue
        t = STRtree(ii)
        hit = None
        for a, i in enumerate(ii):
            for b in t.query(i, predicate='intersects'):
                b = int(b)
                if b <= a:
                    continue
                j = ii[b]
                lo, hi = sorted((i.area, j.area))
                if lo < SAME * hi:
                    continue
                if i.intersection(j).area < OVER * lo:
                    continue
                d = i.centroid.distance(j.centroid)
                if d >= SHIFT:
                    hit = (i, d)
                    break
            if hit:
                break
        if hit:
            i, d = hit
            yield Finding('GF02', 'error',
                          'opening of %.0f mm2 drawn twice, the copy %.1f mm to one side: both loops are cut, the '
                          'opening comes out %.1f mm oversize' % (i.area, d, d), p.key)
