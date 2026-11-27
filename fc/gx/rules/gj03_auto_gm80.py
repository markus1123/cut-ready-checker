"""GJ03: drilled holes drawn at about twice the diameter their drill layer names (diameter typed as the radius)."""
from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx.model import layer_op

RATIO = 1.4     # drawn / named diameter; built files draw holes at the named size (and at most ~1.12x: 6.7 mm
                # circles on 6 mm tool layers, bored out as a circular pocket)


@gx_rule('GJ03', 'Hole drawn far larger than the drill its layer names (diameter typed as the radius)')
def check(g):
    """Layer-driven CAM (Opendesk convention TOP-HOLE-<d>MM-DIAM_<depth>MM, Vectric / Fusion toolpath templates per
    layer) names the bore on the layer: an 8 mm dowel, a 5 mm shelf pin, a 6 mm bolt. CAD circle commands ask for a
    RADIUS by default (AutoCAD CIRCLE: Center, Radius; the diameter needs the D option), so typing the bore size draws
    the circle twice too big. A circle drawn 1.4x or more the named tool is not drawing tolerance (built files draw
    holes at the named size, at most ~1.12x where the tool bores a slightly larger circle): the CAM bores out what is
    drawn, so dowels and pins fall through and screws / bolts have nothing to bite into. (GC05 judges the opposite,
    holes drawn smaller than the tool.)"""
    for p in g.parts:
        worst = None
        for f in p.features:
            if f.op != 'hole' or not f.r:
                continue
            dia = layer_op(f.layer)[2]
            if dia and 2 * f.r >= RATIO * dia and (worst is None or 2 * f.r / dia > worst[0] / worst[1]):
                worst = (2 * f.r, dia, f.layer)
        if worst:
            d, dia, layer = worst
            yield Finding('GJ03', 'error', 'hole drawn Ø%.1f on layer %s, %.1fx the %.1f mm bore that layer names '
                          '(diameter typed as the radius?): the fixing falls through / does not hold'
                          % (d, layer, d / dia, dia), p.key)
