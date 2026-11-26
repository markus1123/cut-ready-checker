"""GI04: a pocket on a layer that names no depth, in a file whose other pockets take their depth from the layer."""
import re
from fc.core import Finding
from fc.gx.core import gx_rule

MIN_AREA = 100.0     # mm2: smaller loops are marks
DEPTH_WORD = re.compile(r'(?i)\d+(?:[.,]\d+)?\s*MM')   # any depth / size stated in the layer name


@gx_rule('GI04', 'Pocket on a layer with no depth while the file\'s other pockets name theirs')
def check(g):
    """Files cut with layer-driven CAM (Opendesk TOP-POCKET-INSIDE_9.000MM, Vectric toolpath templates, Fusion /
    SheetCAM layer-to-operation maps) carry each pocket's depth in its layer name: that is the only place the
    machinist gets it from. When a file names the depth on its other pockets (2+) but one pocket sits on a pocket
    layer whose name states no depth at all (the suffix lost when the layer was renamed or merged), CAM has no
    depth for it: it is skipped (the housing is missing at assembly) or gets the template default, often the full
    sheet (the housing is cut through). Layers that state the depth in another form ('2MM_POCKET_1MM_CUTTER')
    are fine; files that never name pocket depths are left alone (their depths come from a drawing, not the file)."""
    pk = [(p, f) for p in g.parts for f in p.features
          if f.op == 'pocket' and f.geom is not None and not f.geom.is_empty and f.geom.area > MIN_AREA]
    if len([1 for _, f in pk if f.depth]) < 2:
        return
    done = set()
    for p, f in pk:
        if f.depth or DEPTH_WORD.search(f.layer or '') or p.key in done:
            continue
        done.add(p.key)
        yield Finding('GI04', 'error', 'pocket on layer "%s" names no depth while the file\'s other pockets do: '
                      'layer-driven CAM skips it or cuts it to a default depth' % f.layer, p.key)
