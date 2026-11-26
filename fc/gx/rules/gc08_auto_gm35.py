from fc.gx import limits
from fc.core import Finding
from fc.gx.core import gx_rule
from shapely.strtree import STRtree

WEB = limits.FINEST         # mm: 1/16" - less sheet than the finest end mill is wide; built designs keep >= 7.4 mm
TOUCH = 0.3       # mm: closer than this the two openings share a cut line (one opening drawn in two pieces)
MIN_OPEN = 50.0   # mm2: smaller loops are marks / lettering
MIN_PART = 2500.0  # mm2 (~50 x 50 mm): smaller loops with openings are logos / lettering, not furniture parts
LASER = 1.5       # mm: an opening that a 3 mm disc does not fit in = a laser / waterjet file, not a router file
MAX_PAIRS = 2     # more tight pairs = a deliberate lattice / laser pattern
SCALE_MODEL = 300.0   # mm: a unit-less furniture file whose BIGGEST part is shorter than this is a 1:10 / cm drawing
FRAME_OPENINGS, FRAME_HOLDS = 20, 5   # a plain rectangle with 20+ 'openings' and 5+ parts inside them = layout border


@gx_rule('GC08', 'Sheet web between two through openings thinner than any cutter')
def check(g):
    """Two openings side by side leave a bridge of sheet between them, cut on both sides. Ply / MDF under ~1.6 mm
    wide (less than the finest 1/16" end mill) is crushed or torn out by the cutter while the second opening is cut,
    or snaps as soon as the parts sitting in the two slots are loaded: the openings merge and both joints go loose
    (Opendesk / WikiHouse guides keep about a sheet thickness between slots; built designs in the corpus keep 7.4 mm
    or more). Openings closer than 0.3 mm share a cut line and are one opening. Laser files (openings a 1/8" bit
    cannot enter) and lattices with many tight pairs are deliberate patterns for another process and are left alone.
    Narrowed (misreadings on real files):
      * drawing frame / layout border: a plain 4-corner rectangle drawn around a whole nest (Kadushin files) is read
        as one big part whose 'openings' are the real parts, so the gap between two nested PARTS looks like a web
        between two openings; part spacing is G10's job.
      * scale drawings: no unit header and the biggest part under 300 mm - furniture drawn at 1:10 or in cm, so a
        '1 mm' web is really 10 mm; an absolute mm limit does not apply at unknown scale.
      * logos / licence marks: a part under ~50 x 50 mm (e.g. the 29 mm CC mark - a disc with two 'C' openings -
        printed on Kadushin's sheets) is a label, not a furniture part; same size floor as GB01 / G10."""
    spans = [max(p.outer.bounds[2] - p.outer.bounds[0], p.outer.bounds[3] - p.outer.bounds[1]) for p in g.parts]
    if str(g.units).endswith('?') and spans and max(spans) < SCALE_MODEL:
        return
    for p in g.parts:
        if p.outer.area < MIN_PART:
            continue
        ii = [i for i in p.inner if i.geom_type == 'Polygon' and i.is_valid and i.area > MIN_OPEN]
        if len(ii) < 2 or len(ii) > 400:
            continue
        x0, y0, x1, y1 = p.outer.bounds
        if len(p.outer.exterior.coords) <= 5 and p.outer.area > 0.99 * (x1 - x0) * (y1 - y0) and \
                len(p.inner) >= FRAME_OPENINGS and sum(1 for q in g.parts if q is not p and
                                                       any(q.outer.within(i) for i in p.inner)) >= FRAME_HOLDS:
            continue
        if any(i.is_valid and i.area > 1 and i.buffer(-LASER).is_empty for i in p.inner):
            continue
        t = STRtree(ii)
        tight = []
        for a, i in enumerate(ii):
            for b in t.query(i.buffer(WEB)):
                b = int(b)
                if b <= a:
                    continue
                d = i.distance(ii[b])
                if TOUCH < d < WEB:
                    tight.append(d)
        if 1 <= len(tight) <= MAX_PAIRS:
            yield Finding('GC08', 'error', 'only %.1f mm of sheet between two openings (need >= %.1f mm): the web is '
                          'torn out when cut or snaps under load' % (min(tight), WEB), p.key)
