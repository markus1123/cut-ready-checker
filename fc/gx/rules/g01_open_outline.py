from fc.core import Finding
from fc.gx.core import gx_rule


@gx_rule('G01', 'Cut contour almost closes but has a gap')
def check(g):
    """An outline on a cut layer whose ends are < 2 mm apart is a part the export failed to join: CAM can't
    run a closed profile, so the part isn't cut out (or the tool takes the wrong side)."""
    for line, layer in g.open_chains:
        a, b = line.coords[0], line.coords[-1]
        gap = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        if line.length > 50 and gap < 2:
            yield Finding('G01', 'error', 'open contour on %s: %.0f mm long, ends %.2f mm apart' % (layer, line.length, gap),
                          (round(line.centroid.x / 10), round(line.centroid.y / 10)))
