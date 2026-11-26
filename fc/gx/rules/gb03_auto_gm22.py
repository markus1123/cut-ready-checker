from fc.gx import limits
import math
from fc.core import Finding
from fc.gx.core import gx_rule

BIT_MIN = limits.BIT_MIN     # mm, 1/8": smallest router bit that cuts through furniture sheet (docs/rules-from-manuals.md s5)
MAX_GLYPH = 25.0    # mm: a glyph of a part label is at most this long (labels are 5-20 mm tall)
LINK = 25.0         # mm: glyphs of one word / label sit closer than this to each other
MIN_GLYPHS = 3      # a label has several glyphs; one or two narrow slivers are something else
MAX_FILE = 20       # a file with more sub-bit openings than this is a laser job throughout (the beam cuts them):
                    # wrong machine for the whole file, not a label slipped onto the cut layer
MIN_PART = 2500.0   # mm2: smaller loops are not furniture parts
MODEL_L = 250.0     # mm: a drawing whose largest part is shorter than this is a scale model / tabletop craft piece
ROUTER_T = 9.0      # mm: sheet at least this thick is router sheet whatever the drawing's size


def _glyph(i):
    """True if opening i is a small, non-round closed loop that no 1/8" bit fits into anywhere."""
    if i.is_empty or i.geom_type != 'Polygon' or not i.is_valid or i.area < 1.0:
        return False
    minx, miny, maxx, maxy = i.bounds
    w, h = maxx - minx, maxy - miny
    if max(w, h) > MAX_GLYPH:
        return False
    if min(w, h) > 0 and min(w, h) / max(w, h) > 0.85 and i.area > 0.7 * math.pi / 4 * w * h:
        return False                         # round: a drilled / plunged hole, G05 judges those
    return i.buffer(-BIT_MIN / 2).is_empty


def _clusters(pts):
    n = len(pts); seen = [False] * n; out = []
    for s in range(n):
        if seen[s]: continue
        seen[s] = True; stack = [s]; comp = []
        while stack:
            a = stack.pop(); comp.append(a)
            for b in range(n):
                if not seen[b] and math.dist(pts[a], pts[b]) <= LINK:
                    seen[b] = True; stack.append(b)
        out.append(comp)
    return out


@gx_rule('GB03', 'Lettering on the through-cut layer (label glyphs no router bit can cut)')
def check(g):
    """Part labels and markings belong on an engrave / mark layer (V-bit or pen, a fraction of a mm deep). When a
    label is exploded to outlines and left on the cut layer, CAM treats every glyph as a through opening: the
    strokes are 1-2 mm wide, narrower than the smallest bit that cuts through sheet (1/8" = 3.175 mm), so the
    router either skips them, plunges a hole the size of the bit at each, or snaps a thin bit trying - and
    whatever is cut goes through the visible face of the part, with loose letter centres thrown by the cutter.
    Ponoko / SendCutSend file preparation and Opendesk's layer conventions all say: text on an engrave layer, never
    on the cut layer. Recognised as a cluster of >= 3 small (<= 25 mm), non-round closed openings close together
    in one part, none wide enough for a 1/8" bit. Files full of such openings (> 20) are laser jobs throughout and
    are left alone; round ones are holes (G05).
    Narrowed after reading real files from other designers:
      * drawings whose largest part is under 250 mm (and no stated / slot-derived sheet of 9 mm or more) are scale
        models, doll's-house furniture, cake toppers and 3 mm desk toys from laser-file sites: cut on a laser, which
        cuts (or vector-engraves) 1-2 mm strokes as drawn - the router-bit premise of this rule does not apply.
        Full-size furniture always has a part (seat, leg, side) longer than that."""
    if not g.parts:
        return
    L = max(max(p.outer.bounds[2] - p.outer.bounds[0], p.outer.bounds[3] - p.outer.bounds[1]) for p in g.parts)
    t = g.thickness or g.thickness_est
    if L < MODEL_L and not (t and t >= ROUTER_T):
        return
    per_part = []
    total = 0
    for p in g.parts:
        if p.outer.area < MIN_PART:
            continue
        gl = [i for i in p.inner if _glyph(i)]
        total += len(gl)
        if len(gl) >= MIN_GLYPHS:
            per_part.append((p, gl))
    if total > MAX_FILE:
        return
    for p, gl in per_part:
        pts = [(i.centroid.x, i.centroid.y) for i in gl]
        big = max(_clusters(pts), key=len)
        if len(big) >= MIN_GLYPHS:
            yield Finding('GB03', 'error',
                          '%d small closed outlines (strokes narrower than a 1/8" bit) clustered on the cut layer: '
                          'a label / lettering that will be cut through the part - move it to an engrave layer'
                          % len(big), p.key)
