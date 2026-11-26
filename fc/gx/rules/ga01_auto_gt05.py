from fc.core import Finding
from fc.gx.core import gx_rule

TINY_PART = 38.1      # mm (1.5"): a cut file whose BIGGEST part is smaller than this holds no furniture part at all
MIN_LEN_T = 8.0       # a multi-part cut file whose longest part is < 8 sheet thicknesses cannot be furniture
MODEL_SHEET = 4.0     # mm: a file that states its sheet is this thin (3 mm acrylic / model ply) is a small-object file
PATTERN_N = 100       # a file of this many loops ...
PATTERN_SPREAD = 20.0 # ... spread over 20x the size of the biggest one is an ornament / engraving pattern


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
    Reported once per file, on the biggest part.
    Narrowed (misreadings on real files):
      * the file states a sheet of 4 mm or less (e.g. '3mm' in its name): laser acrylic / model ply for small
        hardware (cogs, stays, tee bars of a tensegrity table) - small parts are the design, not a unit mix-up;
        no furniture panel is cut from 3 mm sheet.
      * 100+ tiny loops spread over 20x the size of the biggest one: an ornament / carving pattern (dots, petals)
        laid out at its real size, not a shrunk furniture nest - a shrunk nest keeps its big parts big relative
        to the layout."""
    parts = [p for p in g.parts if p.outer is not None and not p.outer.is_empty]
    if not parts:
        return
    if g.thickness and g.thickness <= MODEL_SHEET:
        return
    def span(p):
        x0, y0, x1, y1 = p.outer.bounds
        return max(x1 - x0, y1 - y0)
    big = max(parts, key=span)
    L = span(big)
    why = None
    if len(parts) >= PATTERN_N:
        x0 = min(p.outer.bounds[0] for p in parts); y0 = min(p.outer.bounds[1] for p in parts)
        x1 = max(p.outer.bounds[2] for p in parts); y1 = max(p.outer.bounds[3] for p in parts)
        if max(x1 - x0, y1 - y0) >= PATTERN_SPREAD * L:
            return
    if L < TINY_PART:
        why = 'biggest part is only %.1f mm long' % L
    elif g.thickness and len(parts) >= 2 and L < MIN_LEN_T * g.thickness:
        why = 'biggest part %.1f mm is under %d x the %.0f mm sheet thickness' % (L, MIN_LEN_T, g.thickness)
    if why:
        yield Finding('GA01', 'error', 'drawing at toy scale - unit mix-up? ' + why, big.key)
