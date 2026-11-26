"""GJ05: a counterbore whose wide bore is drilled deeper than the narrow hole inside it (sizes / depths swapped)."""
from fc.core import Finding
from fc.gx.core import gx_rule

CENTRE = 0.2     # mm: circles this close are one stepped bore
STEP = 1.0       # mm: the wider bore must be at least this much wider in diameter to be a head bore
DEPTH = 0.5      # mm: deeper by more than this is not drawing noise


def _depth(p, f, th):
    if f.depth is not None:
        return f.depth
    if any(f.geom is i for i in p.inner):
        return th          # a circle on a through-cut layer goes through
    return None


@gx_rule('GJ05', 'Stepped bore with the wide bore deeper than the narrow one (counterbore and through hole swapped)')
def check(g):
    """A counterbored or stepped fixing is a narrow bore for the shank (through, or deep) and a wider, shallower
    bore for the head, washer or cam housing round it (Häfele / Hettich connector drilling data: bolt hole + head
    bore with their own diameters and depths; Opendesk HOLE / POCKET layers per diameter and depth). When the wider
    of two concentric bores is drilled DEEPER than the narrow one, the narrow bore is machined away inside the wide
    one and does nothing: the head bore goes right through, so the screw or bolt head pulls through the part (or
    the cam has no floor) - the sizes or the depth layers were swapped. Built files always drill the narrower of two
    concentric bores deeper (or both to the same depth). Bores of unknown depth are not judged."""
    th = g.thickness or g.thickness_est
    for p in g.parts:
        cs = [f for f in p.features if f.r and f.op in ('hole', 'pocket') and f.geom is not None and not f.geom.is_empty]
        if len(cs) > 2000:
            continue
        hit = None
        for a in cs:
            da = _depth(p, a, th)
            if da is None:
                continue
            ca = a.geom.centroid
            for b in cs:
                if b is a or 2 * (b.r - a.r) < STEP:
                    continue
                db = _depth(p, b, th)
                if db is None or db <= da + DEPTH or b.geom.centroid.distance(ca) >= CENTRE:
                    continue
                hit = (a, b, da, db)
                break
            if hit:
                break
        if hit:
            a, b, da, db = hit
            yield Finding('GJ05', 'error', 'stepped bore: the Ø%.1f bore is %.1f mm deep but the Ø%.1f bore inside it '
                          'only %.1f mm - the wide bore goes deeper, so the head / cam has no seat (counterbore and '
                          'hole swapped?)' % (2 * b.r, db, 2 * a.r, da), p.key)
