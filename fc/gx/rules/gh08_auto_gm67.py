"""GH08: a housing (dado) pocket narrower than the stated sheet thickness."""
import math
from fc.core import Finding
from fc.gx.core import gx_rule

TIGHT = 1.2     # mm under the stated thickness. Metric "18 mm" ply is often really 17.2-17.5 mm, so designers draw
                # housings up to 0.8 mm under nominal for the measured sheet (built designs do); 1.2 mm or more under
                # nominal fits no sheet sold under that nominal (EN 315 tolerance is about +/-0.5 mm).
LOW = 0.85      # narrower than 85 % of the sheet is a housing for a THINNER panel (back, drawer bottom), not this sheet


def _axes(poly):
    r = poly.minimum_rotated_rectangle
    if r.geom_type != 'Polygon':
        return None
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return r, min(a, b), max(a, b)


@gx_rule('GH08', 'Housing (dado) pocket narrower than the sheet that sits in it')
def check(g):
    """A housing / dado / trench pocket takes the edge of a mating sheet of the file's stated thickness. Drawn 1.2 mm
    or more narrower than that sheet (but still at least 85 % of it, so it is meant for that sheet and not for a
    thinner back panel), the shelf or divider cannot be pushed in, and sanding 1-3 mm off a sheet edge or chiselling
    every housing wider on site is not a repair (Opendesk / WikiHouse making notes: housings drawn at the measured
    sheet thickness plus clearance; EN 315 plywood thickness tolerances). Only judged when the thickness is stated
    (manifest, file name or Opendesk through-cut layer): a guessed thickness is not reliable enough for an error."""
    th = g.thickness
    if not th or not g.thickness_source:
        return
    for p in g.parts:
        for f in p.features:
            if f.op != 'pocket' or f.r or f.geom is None or f.geom.is_empty or f.geom.geom_type != 'Polygon':
                continue
            ax = _axes(f.geom)
            if ax is None:
                continue
            r, w, L = ax
            if L < 2 * w or f.geom.area < 0.8 * r.area:
                continue
            if LOW * th <= w <= th - TIGHT:
                yield Finding('GH08', 'error',
                              '%.1f mm wide housing pocket for %.1f mm sheet: %.1f mm too tight, the mating part will '
                              'not go in' % (w, th, th - w), p.key)
                break
