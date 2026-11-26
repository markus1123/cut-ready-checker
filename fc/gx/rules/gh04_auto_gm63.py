"""GH04: a drilled hole that breaks into the wall of a through opening in the same part."""
from fc.core import Finding
from fc.gx.core import gx_rule

R_MAX = 12.0        # drilled bores (screws, dowels, pins, bolts); bigger circles are cut-outs
MIN_AREA = 100.0    # mm^2: openings smaller than this are other bores, not slots / cut-outs
PEN_MIN = 0.2       # mm: less is drawing tolerance (the bore just touches the wall)
PEN_FRAC = 0.6      # a bore that reaches past 60 % of its radius into the opening is a deliberate keyhole / relief


@gx_rule('GH04', 'Drilled hole breaks into the wall of a slot / cut-out')
def check(g):
    """A screw, dowel or bolt bore needs solid material all round it. One that cuts a little way into the wall of a
    neighbouring slot or cut-out leaves a half-moon bite in the wall: the fixing has nothing to grip on that side,
    the drill wanders into the void and tears the edge, and the sheet that sits in the slot has a gap there - the
    fixing pulls out and the joint works loose (Häfele / Hettich drilling guides: bores fully in solid board;
    Opendesk: keep fixings clear of slots). Bores that reach more than 60 % of their radius into the opening are
    deliberate keyholes / reliefs and are not judged; built designs keep >= 2 mm between bores and openings."""
    for p in g.parts:
        ops = [i for i in p.inner if i.area >= MIN_AREA]
        if not ops:
            continue
        for f in p.features:
            if f.op != 'hole' or not f.r or f.r > R_MAX or f.geom is None or f.geom.is_empty:
                continue
            c = f.geom.centroid
            for i in ops:
                if i is f.geom or i.equals(f.geom) or not f.geom.intersects(i) or f.geom.within(i):
                    continue
                if i.contains(c):
                    continue
                pen = f.r - i.exterior.distance(c)
                if PEN_MIN < pen < PEN_FRAC * f.r and f.geom.intersection(i).area > 0.5:
                    yield Finding('GH04', 'error',
                                  'dia %.1f mm bore cuts %.1f mm into the wall of a %.0f mm^2 opening: no material for '
                                  'the fixing on that side and the wall tears out' % (2 * f.r, pen, i.area), p.key)
                    break
            else:
                continue
            break
