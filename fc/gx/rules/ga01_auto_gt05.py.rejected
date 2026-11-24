from fc.core import Finding
from fc.gx.core import gx_rule

TINY_PART = 38.1      # mm (1.5"): a cut file whose BIGGEST part is smaller than this holds no furniture part at all
MIN_LEN_T = 8.0       # a multi-part cut file whose longest part is < 8 sheet thicknesses cannot be furniture


@gx_rule('GA01', 'Drawing at toy scale (inch/mm or cm/mm unit mix-up)')
def check(g):
    """Most furniture DXFs have no unit header, or a wrong one: a file drawn in inches and read as mm comes out
    25.4x too small, and the router cuts toy-sized parts from a whole sheet. The scale is wrong when the geometry
    contradicts the physical sheet and tool:
      * the biggest part is under 1.5" (38 mm) - no flat-pack furniture is made only of parts that small
        (the smallest built designs in the corpus are joint test coupons of 68 mm and up);
      * the file states its sheet thickness t (layer depth, manifest or file name) and has several parts, yet no
        part is longer than 8 t - slot-together parts need a length many times the sheet thickness;
    (Router-impossible sub-1.6 mm detail in a tiny file would be a third sign, but laser-cut trinkets in the corpus
    have that legitimately, so it is not used.)
    Reported once per file, on the biggest part."""
    parts = [p for p in g.parts if p.outer is not None and not p.outer.is_empty]
    if not parts:
        return
    def span(p):
        x0, y0, x1, y1 = p.outer.bounds
        return max(x1 - x0, y1 - y0)
    big = max(parts, key=span)
    L = span(big)
    why = None
    if L < TINY_PART:
        why = 'biggest part is only %.1f mm long' % L
    elif g.thickness and len(parts) >= 2 and L < MIN_LEN_T * g.thickness:
        why = 'biggest part %.1f mm is under %d x the %.0f mm sheet thickness' % (L, MIN_LEN_T, g.thickness)
    if why:
        yield Finding('GA01', 'error', 'drawing at toy scale - unit mix-up? ' + why, big.key)
