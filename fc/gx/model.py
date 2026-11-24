"""Generic design model: read ANY CNC furniture DXF (not just our generator's) into parts.

A GDesign is what geometry-only rules (fc/gx/rules) look at:
  parts       list of Part: outer outline + inner through-cuts + drilled holes + pockets, in mm
  open_chains cut-layer geometry that does not close into a loop (the machine can't cut a part from it)
  thickness   sheet thickness in mm if STATED (manifest, file/folder name, or the deepest through-cut on an
              Opendesk-style layer); thickness_est = that or a guess from the most common slot width
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
CACHE = os.environ.get('FC_CACHE') or os.path.join(HERE, 'corpus', 'cache')
VERSION = 8   # bump to invalidate the cache when parsing changes

SKIP = re.compile(r'(?i)noprint|note|text|dim|board|border|defpoints|tolerance|title|frame|label|annot|hatch|center')
STOCK = [(2440, 1220), (2500, 1250), (3050, 1525), (2800, 2070), (2400, 1200)]   # common sheet formats, mm
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
    thickness_source: Optional[str] = None   # where `thickness` comes from: 'manifest' | 'filename' | 'layer' | None
    thickness_est: Optional[float] = None    # GUESS from the most common slot width (files with 2 sheet thicknesses
                                             # fool it): fine for warnings / choosing what to look at, not for errors
    notes: List[str] = field(default_factory=list)
    units_declared: Optional[str] = None     # set when the header's units were overridden as implausible (see load)


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
    """Join segments end to end into loops. Ends match when they are within eps (checked in the 3x3 grid cells
    around a point: plain rounding split points 0.001 mm apart that straddle a cell edge, leaving 'open'
    contours whose ends touch)."""
    key = lambda p: (round(p[0] / eps), round(p[1] / eps))
    ends = {}
    for i, (pts, _) in enumerate(segs):
        ends.setdefault(key(pts[0]), []).append((i, 0)); ends.setdefault(key(pts[-1]), []).append((i, 1))
    def near(p):
        kx, ky = key(p)
        for dx in (0, -1, 1):
            for dy in (0, -1, 1):
                for j, s in ends.get((kx + dx, ky + dy), []):
                    q = segs[j][0][0 if s == 0 else -1]
                    if (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 <= (1.5 * eps) ** 2:
                        yield j, s
    close = lambda a, b: (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 <= (1.5 * eps) ** 2
    used, loops, opens = set(), [], []
    for i, (pts, layer) in enumerate(segs):
        if i in used: continue
        used.add(i)
        if close(pts[0], pts[-1]) and len(pts) > 2:
            loops.append((pts, layer)); continue
        line = list(pts); start = pts[0]; closed = False
        for _ in range(200000):
            nxt = [(j, s) for j, s in near(line[-1]) if j not in used]
            if not nxt: break
            j, s = nxt[0]; used.add(j); q = segs[j][0] if s == 0 else segs[j][0][::-1]
            line += q[1:]
            if close(line[-1], start): closed = True; break
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
    th = meta.get('thickness_mm'); th_src = meta.get('thickness_source') if th else None
    if not th:
        ds = [layer_op(l)[1] for _, l in polys if layer_op(l)[0] in ('cut', 'cut_outside', 'cut_inside') and (layer_op(l)[1] or 0) >= 3]
        th = max(ds) if ds else None
        th_src = 'layer' if th else None
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
    # an EMPTY (or lone) rectangle the size of a stock sheet is the sheet outline (e.g. 'REVERSE FACE'), not a part
    for i, (p, layer) in enumerate(polys):
        if parent[i] is not None: continue
        minx, miny, maxx, maxy = p.bounds
        w, h = max(maxx - minx, maxy - miny), min(maxx - minx, maxy - miny)
        if p.area > 0.99 * w * h and any(abs(w - a) <= 0.02 * a and abs(h - b) <= 0.02 * b for a, b in STOCK) \
                and not kids.get(i):
            parent[i] = -1; notes.append('empty sheet outline on layer %s' % layer)
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
    g = GDesign(id=did or os.path.basename(fn), path=fn, units=units, meta=meta, parts=parts,
                open_chains=opens_mm, thickness=th, sheet=sheet, notes=notes, thickness_source=th_src)
    g.thickness_est = g.thickness or slot_thickness(g)
    return g


def slot_widths(g):
    """Widths of straight rectangular openings / edge notches 3-40 mm wide and >= 1.8x as long (candidate slots)."""
    out = []
    for p in g.parts:
        for i in p.inner:
            r = i.minimum_rotated_rectangle
            if r.geom_type != 'Polygon': continue
            c = list(r.exterior.coords)
            a = math.dist(c[0], c[1]); b = math.dist(c[1], c[2]); w, L = min(a, b), max(a, b)
            if 3 <= w <= 40 and L >= 1.8 * w and i.area >= 0.8 * r.area:
                out.append(round(w, 1))
    return out


def slot_thickness(g, min_count=4):
    """Sheet thickness estimate: the most common slot width, if at least `min_count` slots agree within 0.3 mm
    and it is a plausible furniture sheet (6-30 mm). Press-fit slots are drawn at t + 0-0.5 mm, so this
    over-estimates t by up to ~0.5 mm. None when the file has no clear slot family."""
    ws = sorted(w for w in slot_widths(g) if 6 <= w <= 30)
    best = None
    for w in ws:
        n = sum(1 for x in ws if abs(x - w) <= 0.3)
        if n >= min_count and (best is None or n > best[1]): best = (w, n)
    return best[0] if best else None


def _longest(g):
    return max((max(p.outer.bounds[2] - p.outer.bounds[0], p.outer.bounds[3] - p.outer.bounds[1]) for p in g.parts), default=0)


def _plausible(g):
    if not g.parts: return True
    L = max(max(p.outer.bounds[2] - p.outer.bounds[0], p.outer.bounds[3] - p.outer.bounds[1]) for p in g.parts)
    return 100 <= L <= 3200


def load(fn, units='mm', meta=None, did=None):
    """parse() with an on-disk cache. If the units (guessed when the file has no $INSUNITS, or declared in its
    header) give furniture-implausible sizes - a 39 m chair, a 2.4 km sheet - try mm / inch / cm and keep the first
    plausible one. A wrong DECLARED header is recorded in g.units_declared + g.notes: rule G15 reports it as a
    warning (the operator picks units on import), instead of every size rule misfiring on 1000x parts."""
    g = _load(fn, units, meta, did)
    guessed = units.endswith('?')
    # a declared header is only overridden when it makes the drawing absurdly LARGE (m or in on mm geometry):
    # small declared sizes are real (joint test pieces are 50-100 mm)
    if not _plausible(g) and (guessed or _longest(g) > 3200):
        for u in ('mm?', 'in?', 'cm?'):
            if u.rstrip('?') == units.rstrip('?'): continue
            if not guessed and SCALE[u] >= SCALE.get(units, 1.0): continue
            g2 = _load(fn, u, meta, did)
            if _plausible(g2):
                if guessed:
                    g2.notes.append('unitless file read as %s (guess %s gave implausible sizes)' % (u, units))
                else:
                    g2.units_declared = units
                    g2.notes.append('header says %s but sizes only make sense in %s' % (units, u.rstrip('?')))
                return g2
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
