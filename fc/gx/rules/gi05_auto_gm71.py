"""GI05: counterbore too small for any bolt head / nut / washer over its hole."""
from fc.core import Finding
from fc.gx.core import gx_rule

CENTRE = 0.5      # mm: pocket and hole concentric within this
MIN_STEP = 2.0    # mm: counterbore diameter must exceed the hole by more than this to seat anything


@gx_rule('GI05', 'Counterbore barely larger than its hole: no seat for the bolt head / nut / washer')
def check(g):
    """A round pocket concentric with a smaller drilled / through hole is a counterbore: it sinks a bolt head,
    barrel nut, T-nut flange or washer below the face. Every one of those is much wider than the shank hole:
    ISO 4762 socket heads are 1.5-1.7 x the thread (M6: 10 mm, M8: 13 mm), DIN 974-1 counterbores M6 11 mm over a
    6.6 mm hole (+4.4), washers 2 x the thread; built designs in the corpus step 4-11 mm. A counterbore less than
    2 mm larger in diameter than its hole seats nothing: the head stands proud of the face (on a table top or a
    seat), the joint cannot be pulled tight, and the 1 mm ledge just crumbles."""
    for p in g.parts:
        hs = [h for h in p.features if h.op == 'hole' and h.r and h.geom is not None]
        if not hs: continue
        for f in p.features:
            if f.op != 'pocket' or not f.r or f.geom is None: continue
            c = f.geom.centroid
            inner = [h for h in hs if h.r < f.r and h.geom.centroid.distance(c) < CENTRE]
            if not inner: continue
            h = max(inner, key=lambda h: h.r)
            if 2 * (f.r - h.r) < MIN_STEP:
                yield Finding('GI05', 'error', 'counterbore dia %.1f mm over a dia %.1f mm hole: %.1f mm step seats no '
                              'bolt head, nut or washer' % (2 * f.r, 2 * h.r, 2 * (f.r - h.r)), p.key)
                break
