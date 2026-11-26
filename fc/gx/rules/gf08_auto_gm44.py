import math, os, re
from fc.core import Finding
from fc.gx.core import gx_rule
from fc.gx.rules.g06_auto_gm01 import _slot_width, ply_tol
from fc.gx.model import layer_op

DIMS = re.compile(r'(?<![\d.])(\d{3,4})x(\d{3,4})x(\d{3,4})(?![\d.])')   # Opendesk: ..._STD_410x507x755_... (W x D x H mm)
SLACK = 1.03    # a part may reach the product's full size (tops, sides); 3 % more is no drawing tolerance
RATIO = (1.25, 1.45)   # every slot this many times the stated sheet thickness: the drawing, not the fit, is off
FIT_HI = 1.6    # mm over nominal: the loosest slot fit seen in built designs


def _slots_scaled(g):
    """-> (median slot width, n) when the file states its sheet thickness, has >= 3 slots for a mating sheet, none
    of them fits that sheet, and their median is 1.25-1.45x the sheet; else None."""
    th = g.thickness
    if not th or g.thickness_source is None or th < 3:
        return None
    ws = sorted(w for p in g.parts for i in p.inner for w in [_slot_width(i)] if w is not None and 0.9 * th <= w <= 1.6 * th)
    if len(ws) < 3 or any(th - ply_tol(th) <= w <= th + FIT_HI for w in ws):
        return None
    med = ws[len(ws) // 2]
    return (med, len(ws)) if RATIO[0] * th <= med <= RATIO[1] * th else None


def _holes_scaled(g):
    """-> (median ratio, n) when >= 3 holes sit on layers that name their drill (Opendesk HOLE-<d>MM-DIAM) and the
    median drawn / named diameter is 1.25-1.45; else None."""
    rs = sorted(2 * f.r / d for p in g.parts for f in p.features if f.op == 'hole' and f.r
                for d in [layer_op(f.layer)[2]] if d)
    if len(rs) < 3:
        return None
    med = rs[len(rs) // 2]
    return (med, len(rs)) if RATIO[0] <= med <= RATIO[1] else None


@gx_rule('GF08', 'Drawing scaled wrong: parts bigger than the stated product, or every slot a fixed ratio off the sheet')
def check(g):
    """No part of a piece of furniture can be longer than the piece itself. Opendesk-style file names state the
    finished product's overall size in mm (REG_SCH_STD_410x507x755: width x depth x height); built files reach
    exactly 1.00x of the largest of those with their longest part (tops, sides), never more. A part longer than the
    product's largest dimension by more than 3 % means the drawing was scaled on the way to DXF - 72 dpi points read
    as 96 dpi pixels (1.333x), an inch / mm or cm slip, a 'scale to fit' on export - so every part, slot and hole is
    cut at the wrong size and nothing fits. Only files whose name states three overall dimensions are judged.
    Second witness of the same error: the file states its sheet thickness (layer depth / name), and not one of its
    slots for a mating sheet fits it - every slot (median) is 1.25-1.45x the sheet, the ratios a px/pt or similar
    scale slip produces, far beyond any fit clearance (built designs: 0-1.5 mm over, i.e. <= 1.13x at 12 mm).
    Third witness: holes on layers that name their drill (Opendesk TOP-HOLE-6.000MM-DIAM) are drawn, as a set
    (median), 1.25-1.45x that drill; built files draw them at most 1.12x (6.7 mm for a 6 mm tool)."""
    hs = _holes_scaled(g)
    if hs:
        r, n = hs
        p = max(g.parts, key=lambda q: q.outer.area)
        yield Finding('GF08', 'error',
                      'the %d holes on drill-named layers are drawn %.2fx the drill their layer names: the drawing is '
                      'scaled wrong (px/pt or unit slip) - every hole and part is the wrong size' % (n, r), p.key)
    sc = _slots_scaled(g)
    if sc:
        med, n = sc
        p = max(g.parts, key=lambda q: q.outer.area)
        yield Finding('GF08', 'error',
                      'none of the %d slots fits the stated %.1f mm sheet: they are %.1f mm (%.2fx) - the drawing is '
                      'scaled wrong (px/pt or unit slip), every joint is loose' % (n, g.thickness, med, med / g.thickness),
                      p.key)
    m = DIMS.search(os.path.basename(g.path or g.id))
    if not m or not g.parts:
        return
    big = max(float(x) for x in m.groups())
    worst = None
    for p in g.parts:
        r = p.outer.minimum_rotated_rectangle
        if r.geom_type != 'Polygon':
            continue
        c = list(r.exterior.coords)
        L = max(math.dist(c[0], c[1]), math.dist(c[1], c[2]))
        if L > SLACK * big and (worst is None or L > worst[0]):
            worst = (L, p)
    if worst:
        L, p = worst
        yield Finding('GF08', 'error',
                      'part is %.0f mm long but the file name gives the whole product as at most %.0f mm (%.2fx): the '
                      'drawing is scaled wrong - every part, slot and hole is cut at the wrong size' % (L, big, L / big),
                      p.key)
