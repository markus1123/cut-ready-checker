"""Generic design model: read ANY CNC furniture DXF (not just our generator's) into parts.

A GDesign is what geometry-only rules (fc/gx/rules) look at:
  parts       list of Part: outer outline + inner through-cuts + drilled holes + pockets, in mm
  open_chains cut-layer geometry that does not close into a loop (the machine can't cut a part from it)
  thickness   sheet thickness in mm if known (manifest, or the deepest through-cut on an Opendesk-style layer)
Layer names are parsed for operation + depth (Opendesk: TOP-CUT-OUTSIDE_18.000MM, TOP-POCKET-INSIDE_9.000MM,
TOP-HOLE-6.000MM-DIAM_14.000MM). Unknown layers are treated as through-cuts.
"""
import os, re, math, pickle, hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import ezdxf
from ezdxf import disassemble, path as zpath
from shapely.geometry import Polygon, LineString, Point
from shapely.strtree import STRtree
from shapely.validation import make_valid

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(HERE, 'corpus', 'cache')
VERSION = 5   # bump to invalidate the cache when parsing changes

SKIP = re.compile(r'(?i)noprint|note|text|dim|board|border|defpoints|tolerance|title|frame|label|annot|hatch|center')
SCALE = {'mm': 1.0, 'mm?': 1.0, 'in': 25.4, 'in?': 25.4, 'cm?': 10.0, 'm': 1000.0}


def layer_op(layer):
    """'TOP-POCKET-INSIDE_9.000MM' -> ('pocket', 9.0, None); 'TOP-HOLE-6.000MM-DIAM_14.000MM' -> ('hole', 14.0, 6.0)."""
    u = layer.upper()
    if SKIP.search(u):
        return 'skip', None, None
    m = re.search(r'_(\d+(?:\.\d+)?)\s*MM\s*$', u)
    depth = float(m.group(1)) if m else None
    dm = re.search(r'HOLE-(\d+(?:\.\d+)?)MM-DIAM', u)
    if 'POCKET' in u: return 'pocket', depth, None
    if 'HOLE' in u or 'DRILL' in u or 'DOWEL' in u: return 'hole', depth, float(dm.group(1)) if dm else None
    if 'CHAMFER' in u or 'ENGRAV' in u or 'ETCH' in u or 'SCORE' in u or 'MARK' in u: return 'engrave', depth, None
    if 'INSIDE' in u: return 'cut_inside', depth, None
    if 'OUTSIDE' in u: return 'cut_outside', depth, None
    return 'cut', depth, None


@dataclass
class Feature:
    op: str                 # 'pocket' | 'hole' | 'engrave'
    geom: object            # shapely Polygon (or Point-buffer for circles)
    depth: Optional[float]  # mm, None = unknown
    layer: str
    r: Optional[float] = None   # radius for circles / drilled holes


@dataclass
class Part:
    outer: Polygon                       # outline (no holes)
    inner: List[Polygon] = field(default_factory=list)   # through-cut openings inside the part (loops + circles)
    features: List[Feature] = field(default_factory=list)
    layer: str = ''
    depth: Optional[float] = None        # cut depth from the layer, if stated

    @property
    def poly(self):
        p = Polygon(self.outer.exterior.coords, [i.exterior.coords for i in self.inner if i.within(self.outer)])
        return p if p.is_valid else make_valid(p)

    @property
    def key(self):
        c = self.outer.centroid
        return (round(c.x / 10), round(c.y / 10))


@dataclass
class GDesign:
    id: str
    path: str
    units: str
    meta: dict
    parts: List[Part]
    open_chains: List[Tuple[LineString, str]]
    thickness: Optional[float]
    sheet: Optional[Polygon] = None
    notes: List[str] = field(default_factory=list)


def _loops(fn, tol):
    doc = ezdxf.readfile(fn)
    segs, circles = [], []
    for e in disassemble.recursive_decompose(doc.modelspace()):
        t = e.dxftype()
        if t in ('TEXT', 'MTEXT', 'DIMENSION', 'HATCH', 'POINT', 'MULTILEADER', 'ATTRIB', 'ATTDEF', 'VIEWPORT', 'IMAGE', 'SOLID', '3DFACE'):
            continue
        layer = e.dxf.layer
        if layer_op(layer)[0] == 'skip':
            continue
        if t == 'CIRCLE':
            circles.append((e.dxf.center.x, e.dxf.center.y, e.dxf.radius, layer)); continue
        try:
            p = zpath.make_path(e)
        except Exception:
            continue
        pts = [(v.x, v.y) for v in p.flattening(tol)]
        if len(pts) >= 2:
            segs.append((pts, layer))
    return segs, circles


def _chain(segs, eps):
    key = lambda p: (round(p[0] / eps), round(p[1] / eps))
    ends = {}
    for i, (pts, _) in enumerate(segs):
        ends.setdefault(key(pts[0]), []).append((i, 0)); ends.setdefault(key(pts[-1]), []).append((i, 1))
    used, loops, opens = set(), [], []
    for i, (pts, layer) in enumerate(segs):
        if i in used: continue
        used.add(i)
        if key(pts[0]) == key(pts[-1]) and len(pts) > 2:
            loops.append((pts, layer)); continue
        line = list(pts); start, cur = key(pts[0]), key(pts[-1]); closed = False
        for _ in range(200000):
            nxt = [(j, s) for j, s in ends.get(cur, []) if j not in used]
            if not nxt: break
            j, s = nxt[0]; used.add(j); q = segs[j][0] if s == 0 else segs[j][0][::-1]
            line += q[1:]; cur = key(q[-1])
            if cur == start: closed = True; break
        (loops if closed and len(line) > 3 else opens).append((line, layer))
    return loops, opens


def parse(fn, units='mm', meta=None, did=None):
    """DXF -> GDesign (mm). Raises on unreadable files."""
    s = SCALE.get(units, 1.0)
    segs, circles = _loops(fn, 0.05 / s)
    loops, opens = _chain(segs, 0.02 / s)
    polys = []
    for pts, layer in loops:
        try:
            p = Polygon([(x * s, y * s) for x, y in pts])
        except Exception:
            continue
        if not p.is_valid: p = p.buffer(0)
        if p.is_empty or p.area < 1.0 or p.geom_type != 'Polygon': continue
        polys.append((p, layer))
    seen, uniq = set(), []          # stacked duplicate loops (common export artefact) - keep one
    for p, layer in polys:
        k = (round(p.area), round(p.centroid.x), round(p.centroid.y))
        if k not in seen: seen.add(k); uniq.append((p, layer))
    polys = sorted(uniq, key=lambda t: -t[0].area)[:6000]
    notes = []
    meta = meta or {}
    th = meta.get('thickness_mm')
    if not th:
        ds = [layer_op(l)[1] for _, l in polys if layer_op(l)[0] in ('cut', 'cut_outside', 'cut_inside') and (layer_op(l)[1] or 0) >= 3]
        th = max(ds) if ds else None
    def op_of(layer):
        op, dep, dia = layer_op(layer)
        if op.startswith('cut') and th and dep and dep < 0.9 * th:
            return 'pocket', dep, dia          # a cut layer that stops part-way = rebate / step, not a through cut
        return op, dep, dia
    # containment depth -> even = part outline, odd = opening in a part
    geoms = [p for p, _ in polys]
    tree = STRtree(geoms) if geoms else None
    parent = [None] * len(polys)
    for i, (p, layer) in enumerate(polys):
        best = None
        for j in (tree.query(p, predicate='within') if tree is not None else []):
            j = int(j)
            if j != i and geoms[j].area > p.area * 1.0001 and (best is None or geoms[j].area < geoms[best].area):
                best = j
        parent[i] = best
    # sheet border: a big rectangle on a cut layer that only holds other parts
    sheet = None
    kids = {}
    for i, pa in enumerate(parent):
        if pa is not None: kids.setdefault(pa, []).append(i)
    for i, (p, layer) in enumerate(polys):
        minx, miny, maxx, maxy = p.bounds
        if p.area > 0.99 * (maxx - minx) * (maxy - miny) and min(maxx - minx, maxy - miny) > 500 and \
                len([k for k in kids.get(i, []) if geoms[k].area > 0.003 * p.area]) >= 3 and parent[i] is None:
            sheet = p; notes.append('sheet border on layer %s' % layer)
            for k in kids.get(i, []): parent[k] = None
            parent[i] = -1
    depth = [0] * len(polys)
    for i in range(len(polys)):
        d, q = 0, parent[i]
        while q is not None and q != -1:
            d += 1; q = parent[q]
        depth[i] = d
    parts, pidx = [], {}
    for i, (p, layer) in enumerate(polys):
        op, dep, dia = op_of(layer)
        if parent[i] == -1: continue
        if depth[i] % 2 == 0 and op in ('cut', 'cut_outside', 'cut_inside'):
            pidx[i] = len(parts); parts.append(Part(outer=Polygon(p.exterior.coords), layer=layer, depth=dep))
    for i, (p, layer) in enumerate(polys):
        if i in pidx or parent[i] == -1: continue
        op, dep, dia = op_of(layer)
        q = parent[i]
        while q is not None and q not in pidx: q = parent[q]
        if q is None:
            touch = [pidx[k] for k in pidx if geoms[k].intersects(p)] if op in ('pocket', 'engrave') else []
            if touch:      # edge rebate drawn across the outline
                parts[max(touch, key=lambda j: parts[j].outer.intersection(p).area)].features.append(Feature(op, p, dep, layer))
            elif op in ('pocket', 'hole', 'engrave'):
                notes.append('%s loop outside any part (%s)' % (op, layer))
            continue
        part = parts[pidx[q]]
        if op in ('pocket', 'hole', 'engrave'):
            part.features.append(Feature(op, p, dep, layer))
        else:
            part.inner.append(p)
    # loops drawn ACROSS a bigger part's outline (notches drawn as separate rectangles, edge rebates): merge into it
    for pt in sorted(parts, key=lambda q: q.outer.area):
        if pt not in parts: continue
        host = [q for q in parts if q is not pt and q.outer.area > pt.outer.area * 6 and q.outer.intersects(pt.outer)
                and not pt.outer.within(q.outer) and q.outer.intersection(pt.outer).area > 0.2 * pt.outer.area]
        if not host: continue
        q = max(host, key=lambda q: q.outer.intersection(pt.outer).area)
        d = q.outer.difference(pt.outer)
        if d.geom_type == 'MultiPolygon': d = max(d.geoms, key=lambda x: x.area)
        if d.is_empty or d.geom_type != 'Polygon': continue
        q.outer = Polygon(d.exterior.coords); parts.remove(pt); notes.append('notch merged into part (%s)' % pt.layer)
    # circles
    pg = [pt.outer for pt in parts]
    ptree = STRtree(pg) if pg else None
    for x, y, r, layer in circles:
        x, y, r = x * s, y * s, r * s
        if r < 0.5:
            continue          # centre marks for hand drilling, not holes
        op, dep, dia = op_of(layer)
        c = Point(x, y).buffer(r, 32)
        hits = [int(j) for j in (ptree.query(Point(x, y), predicate='within') if ptree is not None else [])]
        if not hits:
            if op in ('cut', 'cut_outside') and r > 5:
                parts.append(Part(outer=c, layer=layer, depth=dep)); pg.append(c)   # round part (e.g. a disc seat)
            continue
        part = min((parts[j] for j in hits), key=lambda pt: pt.outer.area)
        if any(c.within(i) for i in part.inner):
            continue
        if op in ('hole', 'pocket', 'engrave'):
            part.features.append(Feature('hole' if op == 'hole' else op, c, dep, layer, r))
        else:
            part.inner.append(c); part.features.append(Feature('hole', c, None, layer, r))
    opens_mm = [(LineString([(x * s, y * s) for x, y in pts]), layer) for pts, layer in opens
                if layer_op(layer)[0] in ('cut', 'cut_outside', 'cut_inside')]
    return GDesign(id=did or os.path.basename(fn), path=fn, units=units, meta=meta, parts=parts,
                   open_chains=opens_mm, thickness=th, sheet=sheet, notes=notes)


def _plausible(g):
    if not g.parts: return True
    L = max(max(p.outer.bounds[2] - p.outer.bounds[0], p.outer.bounds[3] - p.outer.bounds[1]) for p in g.parts)
    return 100 <= L <= 3200


def load(fn, units='mm', meta=None, did=None):
    """parse() with an on-disk cache. Units ending in '?' were guessed (file has no $INSUNITS): if the guess gives
    furniture-implausible sizes, try mm / inch / cm and keep the first plausible one (noted in g.notes).
    Declared units are never overridden: a wrong header is a real fault in the file."""
    g = _load(fn, units, meta, did)
    if units.endswith('?') and not _plausible(g):
        for u in ('mm?', 'in?', 'cm?'):
            if u == units: continue
            g2 = _load(fn, u, meta, did)
            if _plausible(g2):
                g2.notes.append('unitless file read as %s (guess %s gave implausible sizes)' % (u, units)); return g2
    return g


def _load(fn, units='mm', meta=None, did=None):
    h = hashlib.sha1(open(fn, 'rb').read()).hexdigest()
    cf = os.path.join(CACHE, '%s_%s_v%d.pkl' % (h, units.replace('?', 'q'), VERSION))
    if os.path.exists(cf):
        try:
            g = pickle.load(open(cf, 'rb')); g.meta = meta or {}; g.id = did or g.id; g.path = fn
            return g
        except Exception:
            pass
    g = parse(fn, units, meta, did)
    os.makedirs(CACHE, exist_ok=True)
    pickle.dump(g, open(cf, 'wb'))
    return g
