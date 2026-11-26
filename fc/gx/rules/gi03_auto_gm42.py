"""GI03: identical parts, one with every opening shifted - for parts whose openings include a shaped cut-out."""
import shapely
from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx.rules.gf07_auto_gm42 import MIN_PART, SAME, SHIFT, MAX_OPEN, _openings, _has_slot, _transforms, _offset

ROUND = 0.8   # opening area / its smallest enclosing circle: below this it is a shaped cut-out, not a round hole


def _shaped(p):
    """Has the part a non-round opening (handle, cut-out, notch, slot): something drawn as part of the part's shape."""
    for i in p.inner:
        if i.area <= 20 or not i.is_valid: continue
        if i.area < ROUND * shapely.minimum_bounding_circle(i).area:
            return True
    return False


@gx_rule('GI03', 'Identical parts with every opening of one shifted against its outline (shaped cut-outs)')
def check(g):
    """Copies of a part are cut from one drawing: the same handle cut-outs, notches, slots and holes at the same
    places. When one copy has EVERY opening shifted by one and the same 2-40 mm offset relative to its outline, the
    outline was moved or nested without them (openings on a locked / hidden / separate layer, not grouped with the
    outline): it is cut with every cut-out and hole out of place, so handles, hardware and mating parts no longer
    line up with the other parts. GF07 judges parts with a slot for a mating sheet; this rule extends it to parts
    with any shaped (non-round) cut-out - a cut-out is part of the part's drawn shape and is never repositioned per
    copy. Parts with only round holes are left out: built drawer bottoms (Fellesverkstedet) place round pull / screw
    holes per copy, a few mm apart."""
    big = [p for p in g.parts if p.outer.area >= MIN_PART and p.outer.is_valid]
    done = set()
    for x, a in enumerate(big):
        oa = _openings(a)
        if len(oa) < 2 or len(oa) > MAX_OPEN or _has_slot(a) or not _shaped(a):
            continue
        for b in big[x + 1:]:
            if abs(a.outer.area - b.outer.area) > SAME * a.outer.length:
                continue
            ob = _openings(b)
            if len(ob) != len(oa):
                continue
            offs = [_offset(oa, [f(q) for q in ob]) for f in _transforms(a, b)]
            if not offs or 0.0 in offs:
                continue
            s = [o for o in offs if o is not None and SHIFT[0] <= o <= SHIFT[1]]
            if s and (a.key, b.key) not in done:
                done.add((a.key, b.key))
                for k in (a.key, b.key):
                    yield Finding('GI03', 'error',
                                  'all %d openings (incl. shaped cut-outs) of one of two identical parts sit %.1f mm off '
                                  'against the other: an outline was moved without its openings - nothing lines up'
                                  % (len(oa), min(s)), k)
