import re
from fc.core import Finding
from fc.gx.core import gx_rule

SNAP = 0.11     # mm: ends closer than this (~0.1 mm, a router's positioning accuracy) are an export rounding gap
INFO = re.compile(r'(?i)\binfo')   # 'Info' / 'INFO_...' layers carry notes and assembly sketches, not cut paths


@gx_rule('G01', 'Cut contour almost closes but has a gap')
def check(g):
    """An outline on a cut layer whose ends are < 2 mm apart is a part the export failed to join: CAM can't
    run a closed profile, so the part isn't cut out (or the tool takes the wrong side).
    Narrowed (misreadings on real files):
      * gaps up to ~0.1 mm: coordinate rounding in the export (the reader joins ends only within 0.03 mm). That is
        within a furniture router's own positioning accuracy and a tiny fraction of any kerf, and CAM's
        join-open-vectors step closes it on import; a missing piece of outline leaves a gap of a whole segment.
      * layers named 'Info': the designer's information layer (notes, assembly sketches), not a cut layer."""
    for line, layer in g.open_chains:
        if INFO.search(layer):
            continue
        a, b = line.coords[0], line.coords[-1]
        gap = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        if line.length > 50 and SNAP <= gap < 2:
            yield Finding('G01', 'error', 'open contour on %s: %.0f mm long, ends %.2f mm apart' % (layer, line.length, gap),
                          (round(line.centroid.x / 10), round(line.centroid.y / 10)))
