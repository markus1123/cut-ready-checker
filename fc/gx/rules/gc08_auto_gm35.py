from fc.core import Finding
from fc.gx.core import gx_rule
from shapely.strtree import STRtree

WEB = 1.6         # mm: 1/16" - less sheet than the finest end mill is wide; built designs keep >= 7.4 mm
TOUCH = 0.3       # mm: closer than this the two openings share a cut line (one opening drawn in two pieces)
MIN_OPEN = 50.0   # mm2: smaller loops are marks / lettering
LASER = 1.5       # mm: an opening that a 3 mm disc does not fit in = a laser / waterjet file, not a router file
MAX_PAIRS = 2     # more tight pairs = a deliberate lattice / laser pattern


@gx_rule('GC08', 'Sheet web between two through openings thinner than any cutter')
def check(g):
    """Two openings side by side leave a bridge of sheet between them, cut on both sides. Ply / MDF under ~1.6 mm
    wide (less than the finest 1/16" end mill) is crushed or torn out by the cutter while the second opening is cut,
    or snaps as soon as the parts sitting in the two slots are loaded: the openings merge and both joints go loose
    (Opendesk / WikiHouse guides keep about a sheet thickness between slots; built designs in the corpus keep 7.4 mm
    or more). Openings closer than 0.3 mm share a cut line and are one opening. Laser files (openings a 1/8" bit
    cannot enter) and lattices with many tight pairs are deliberate patterns for another process and are left alone."""
    for p in g.parts:
        ii = [i for i in p.inner if i.geom_type == 'Polygon' and i.is_valid and i.area > MIN_OPEN]
        if len(ii) < 2 or len(ii) > 400:
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
