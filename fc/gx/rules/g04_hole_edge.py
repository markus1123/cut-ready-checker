from fc.core import Finding
from fc.gx.core import gx_rule


@gx_rule('G04', 'Drilled hole too close to the part edge')
def check(g):
    """A small through hole whose edge is under 1.5 mm from the outline breaks out when drilled or loaded.
    Blind holes (stated depth < sheet) only need to stay inside the part: Opendesk's lift desk has 6 mm blind
    holes 0.9 mm from the edge and has been built many times."""
    for p in g.parts:
        for f in p.features:
            if f.op == 'hole' and f.r and f.r <= 12:
                blind = f.depth and g.thickness and f.depth < 0.9 * g.thickness
                d = p.outer.exterior.distance(f.geom)
                inside = f.geom.within(p.outer.buffer(0.01))
                if inside and d < (0.3 if blind else 1.5):
                    yield Finding('G04', 'error', 'hole r=%.1f only %.1f mm from edge%s' % (f.r, d, ' (blind)' if blind else ''), p.key)
