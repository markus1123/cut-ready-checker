from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx.model import layer_op

SLACK = 0.5   # mm: a drawn hole may differ from the named tool by drawing rounding; built files stay within -0.0/+0.71


@gx_rule('GC05', 'Hole drawn smaller than the drill its layer names')
def check(g):
    """Layer-driven CAM (Opendesk convention TOP-HOLE-<d>MM-DIAM_<depth>MM, Vectric/Fusion toolpath templates per
    layer) picks the drill from the layer name. A drill cannot make a hole smaller than itself: a circle drawn more
    than 0.5 mm under the layer's tool diameter is drilled at the tool size, so the screw / dowel / pin it was sized
    for has nothing to bite into and the joint is loose. (Drawn LARGER than the tool is fine: the tool bores it out
    as a circular pocket - built Opendesk files do that with 6 mm tools in 6.7 mm holes.)"""
    for p in g.parts:
        worst = None
        for f in p.features:
            if f.op != 'hole' or not f.r:
                continue
            dia = layer_op(f.layer)[2]
            if dia and 2 * f.r < dia - SLACK and (worst is None or 2 * f.r - dia < worst[0] - worst[1]):
                worst = (2 * f.r, dia, f.layer)
        if worst:
            d, dia, layer = worst
            yield Finding('GC05', 'error',
                          'hole drawn Ø%.1f on layer %s: the %.1f mm drill that layer names makes it %.1f mm '
                          'oversize - the fastener will not hold' % (d, layer, dia, dia - d), p.key)
