"""Mined fault TYPES (documented real-world CNC flat-pack failures) applied to real, built designs (train split).
Same format as faults/gx_train.py. The loop's agents may read this file."""
import math
from shapely import affinity
from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points
from fc.gx.mutate import Mut, clone, holes


def _rect_axes(poly):
    """Minimum rotated rectangle of poly -> (rect, width, length, angle of the long side in degrees)."""
    r = poly.minimum_rotated_rectangle
    c = list(r.exterior.coords)
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    if a >= b:
        ang = math.degrees(math.atan2(c[1][1] - c[0][1], c[1][0] - c[0][0]))
    else:
        ang = math.degrees(math.atan2(c[2][1] - c[1][1], c[2][0] - c[1][0]))
    return r, min(a, b), max(a, b), ang


def _slots(p, th):
    """Through openings in p shaped like a slot for a mating sheet: narrow side ~ sheet thickness."""
    out = []
    for i in p.inner:
        if i.area < 50: continue
        r, w, L, ang = _rect_axes(i)
        if 0.95 * th <= w <= 1.3 * th and L >= 1.5 * w and i.area > 0.8 * r.area:
            out.append((i, w, ang))
    return out


def _replace_inner(p, old, new):
    p.inner[p.inner.index(old)] = new
    for f in p.features:
        if f.geom is old: f.geom = new


def _slot_too_narrow(g, rng):
    """Slots drawn to nominal thickness minus 2 mm (e.g. 16 mm slots for 18 mm ply)."""
    if not g.thickness: return None
    g = clone(g); th = g.thickness; n = 0
    for p in g.parts:
        for i, w, ang in _slots(p, th):
            c = i.centroid
            k = (th - 2.0) / w
            m = affinity.rotate(i, -ang, origin=c)
            m = affinity.scale(m, 1.0, k, origin=c)          # narrow axis is y after aligning the long side to x
            m = affinity.rotate(m, ang, origin=c)
            if not m.is_valid or m.is_empty: continue
            _replace_inner(p, i, m); n += 1
    return g if n else None


def _core_rect(i):
    """Core rectangle of a dog-boned opening, or None if i has no dog-bone lobes."""
    r, w, L, ang = _rect_axes(i)
    if w < 6: return None
    rad = min(6.0, 0.3 * w)
    o = i.buffer(-rad).buffer(rad)                             # opening: strips the small corner lobes
    if o.is_empty or o.geom_type != 'Polygon': return None
    core, cw, cL, _ = _rect_axes(o)
    if core.area < 0.8 * i.area or core.area > 0.995 * i.area: return None   # no lobes (or not rectangle-like)
    if not core.buffer(-0.3).within(i): return None
    if i.difference(core).area < 4: return None
    return core


def _no_dogbones(g, rng):
    """Every dog-boned rectangular opening exported with sharp 90-degree inside corners instead."""
    g = clone(g); n = 0
    for p in g.parts:
        for i in list(p.inner):
            core = _core_rect(i)
            if core is None: continue
            _replace_inner(p, i, Polygon(core.exterior.coords)); n += 1
    return g if n else None


def _bores_collide(g, rng):
    """One drilled hole moved so only 0.5 mm of material is left between it and its neighbour bore."""
    g = clone(g)
    cand = []
    for p in g.parts:
        hs = holes(p)
        if len(hs) < 2: continue
        for f in hs:
            others = [h for h in hs if h is not f and h.geom.centroid.distance(f.geom.centroid) > 1]
            if others: cand.append((p, f, min(others, key=lambda h: h.geom.distance(f.geom))))
    rng.shuffle(cand)
    for p, f, h in cand:
        a, b = f.geom.centroid, h.geom.centroid
        d = a.distance(b)
        ra = math.sqrt(f.geom.area / math.pi); rb = math.sqrt(h.geom.area / math.pi)
        target = ra + rb + 0.5
        if d <= target + 1.0: continue                         # already close: nothing to break
        k = (d - target) / d
        m = affinity.translate(f.geom, (b.x - a.x) * k, (b.y - a.y) * k)
        if not m.within(p.outer) or p.outer.exterior.distance(m) < 3: continue
        if any(m.intersects(o) for o in p.inner if o is not f.geom): continue
        if any(m.intersects(o.geom) for o in p.features if o is not f and o is not h and o.op == 'hole'): continue
        if f.geom in p.inner: p.inner[p.inner.index(f.geom)] = m
        f.geom = m
        return g
    return None


def _translate_part(p, dx, dy):
    p.outer = affinity.translate(p.outer, dx, dy)
    olds = list(p.inner)
    p.inner = [affinity.translate(i, dx, dy) for i in olds]
    for f in p.features:
        hit = [k for k, o in enumerate(olds) if f.geom is o]
        f.geom = p.inner[hit[0]] if hit else affinity.translate(f.geom, dx, dy)


def _nest_too_tight(g, rng):
    """One part moved toward its nearest neighbour on the sheet so only 1.5 mm separates them (less than any cutter)."""
    if len(g.parts) < 2: return None
    g = clone(g); gap = 1.5
    order = sorted(g.parts, key=lambda p: -p.outer.area)[:12]
    rng.shuffle(order)
    for a in order:
        others = [p for p in g.parts if p is not a]
        b = min(others, key=lambda p: p.outer.distance(a.outer))
        d = a.outer.distance(b.outer)
        if d < 5: continue                                    # already tight / common-line layout: nothing to break
        pa, pb = nearest_points(a.outer, b.outer)
        k = (d - gap) / d
        dx, dy = (pb.x - pa.x) * k, (pb.y - pa.y) * k
        moved = affinity.translate(a.outer, dx, dy)
        dists = [moved.distance(o.outer) for o in others]
        if min(dists) < gap - 0.2 or min(dists) > gap + 0.2: continue
        if g.sheet is not None and not moved.within(g.sheet): continue
        _translate_part(a, dx, dy)
        return g
    return None


def _faceted_holes(g, rng):
    """Every round through hole (Ø4 mm and up) exported as an 8-sided polyline instead of a true circle/arc."""
    g = clone(g); n = 0
    for p in g.parts:
        for f in holes(p, rmax=40.0):
            if f.r < 2.0 or f.geom not in p.inner: continue
            c = f.geom.centroid
            k0 = math.pi / 8
            oct_ = Polygon([(c.x + f.r * math.cos(k0 + 2 * math.pi * j / 8), c.y + f.r * math.sin(k0 + 2 * math.pi * j / 8))
                            for j in range(8)])
            p.inner[p.inner.index(f.geom)] = oct_; f.geom = oct_; n += 1
    return g if n else None


def _off_sheet(g, rng):
    """A part pushed across the drawn stock-sheet border: 30 mm of it lies outside the material."""
    if g.sheet is None: return None
    g = clone(g); sb = g.sheet.exterior
    cand = [p for p in g.parts if p.outer.within(g.sheet) and p.outer.area > 2000]
    rng.shuffle(cand)
    for p in cand:
        pa, pb = nearest_points(p.outer.exterior, sb)
        d = pa.distance(pb)
        minx, miny, maxx, maxy = p.outer.bounds
        over = min(30.0, 0.3 * min(maxx - minx, maxy - miny))
        if d < 1e-6 or over < 5: continue
        k = (d + over) / d
        dx, dy = (pb.x - pa.x) * k, (pb.y - pa.y) * k
        moved = affinity.translate(p.outer, dx, dy)
        out = moved.difference(g.sheet).area
        if out < 0.05 * moved.area or out > 0.5 * moved.area: continue
        if any(moved.intersects(o.outer) for o in g.parts if o is not p): continue
        _translate_part(p, dx, dy)
        return g
    return None


def _hole_rows(p):
    """Rows of >= 3 same-size drilled holes on one straight line at equal pitch (System 32 / shelf-pin / fitting rows).
    -> list of (row_features, unit direction)."""
    hs = [f for f in holes(p) if f.r]
    rows, seen = [], set()
    for a in hs:
        for b in hs:
            if a is b or round(a.r, 1) != round(b.r, 1): continue
            ca, cb = a.geom.centroid, b.geom.centroid
            d = ca.distance(cb)
            if d < 8: continue
            ux, uy = (cb.x - ca.x) / d, (cb.y - ca.y) / d
            row = [a, b]
            k = 2
            while True:                                       # extend the row a -> b -> ... at the same pitch
                nx, ny = ca.x + ux * d * k, ca.y + uy * d * k
                nxt = [h for h in hs if round(h.r, 1) == round(a.r, 1) and h.geom.centroid.distance(Point(nx, ny)) < 0.3]
                if not nxt: break
                row.append(nxt[0]); k += 1
            if len(row) < 3: continue
            key = frozenset(id(f) for f in row)
            if key in seen: continue
            seen.add(key); rows.append((row, (ux, uy), d))
    return rows


def _row_off_pitch(g, rng):
    """One hole of a regular drilled row (shelf pins, runner/hinge-plate screws, System 32 line) drawn 4 mm off the row line."""
    g = clone(g)
    cand = [(p, row, u, d) for p in g.parts for row, u, d in _hole_rows(p)]
    rng.shuffle(cand)
    for p, row, (ux, uy), _ in cand:
        f = rng.choice(row)
        nx, ny = -uy, ux
        sgn = rng.choice((1, -1))
        for s in (sgn, -sgn):
            m = affinity.translate(f.geom, nx * 4.0 * s, ny * 4.0 * s)
            if not m.within(p.outer) or p.outer.exterior.distance(m) < 3: continue
            if any(m.intersects(o) for o in p.inner if o is not f.geom): continue
            if any(m.distance(o.geom) < 3 for o in p.features if o is not f and o.op in ('hole', 'pocket')): continue
            if f.geom in p.inner: p.inner[p.inner.index(f.geom)] = m
            f.geom = m
            return g
    return None


def _self_intersect(g, rng):
    """A part outline with a small figure-8 kink: the contour crosses itself (overshoot + doubled-back segment)."""
    from shapely.geometry import LineString
    g = clone(g)
    cand = [p for p in sorted(g.parts, key=lambda q: -q.outer.area)[:10] if p.outer.area > 5000]
    rng.shuffle(cand)
    for p in cand:
        ring = p.outer.exterior
        pts = list(ring.coords)[:-1]
        segs = [(i, math.dist(pts[i], pts[(i + 1) % len(pts)])) for i in range(len(pts))]
        segs = [s for s in segs if s[1] > 40]
        if not segs: continue
        i, L = rng.choice(segs)
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % len(pts)]
        tx, ty = (x1 - x0) / L, (y1 - y0) / L
        # outward normal: for a CCW ring the outside is to the right of the travel direction
        nx, ny = (ty, -tx) if ring.is_ccw else (-ty, tx)
        mx, my = x0 + tx * L / 2, y0 + ty * L / 2
        P = lambda a, b: (mx + tx * a + nx * b, my + ty * a + ny * b)
        new = pts[:i + 1] + [P(0, 0), P(8, 5), P(8, 0), P(0, 5), P(0, 2.5), P(10, 0)] + pts[i + 1:]
        poly = Polygon(new)
        if poly.is_valid or LineString(new + [new[0]]).is_simple: continue
        if any(poly.buffer(0).intersects(o.outer) for o in g.parts if o is not p and o.outer.distance(p.outer) < 6): continue
        p.outer = poly
        return g
    return None


def _mirror(geom, cx):
    return affinity.scale(geom, -1.0, 1.0, origin=(cx, 0))


def _handed(p):
    """True if p (outline + one-sided pockets) is clearly NOT congruent to its own mirror image under any 0/90/180/270
    turn: under every turn the mirrored outline differs by > 1 % of its area or the pockets by > 25 %."""
    from shapely.ops import unary_union
    minx, miny, maxx, maxy = p.outer.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    pf = unary_union([f.geom for f in p.features if f.op == 'pocket'])
    mo = _mirror(p.outer, cx); mf = _mirror(pf, cx)
    for ang in (0, 90, 180, 270):
        ro = affinity.rotate(mo, ang, origin=(cx, cy)); rf = affinity.rotate(mf, ang, origin=(cx, cy))
        if ro.symmetric_difference(p.outer).area <= 0.01 * p.outer.area and \
                rf.symmetric_difference(pf).area <= 0.25 * pf.area:
            return False
    return True


def _wrong_hand(g, rng):
    """A part with pockets (one-sided machining) drawn mirror-imaged: the left-hand version of a right-hand part."""
    g = clone(g)
    cand = [p for p in g.parts if p.outer.area > 5000 and any(f.op == 'pocket' and f.geom.area > 30 for f in p.features)]
    rng.shuffle(cand)
    for p in cand:
        if not _handed(p): continue
        minx, miny, maxx, maxy = p.outer.bounds
        cx = (minx + maxx) / 2
        mo = _mirror(p.outer, cx)
        if any(mo.intersects(o.outer) and not o.outer.within(p.outer) and mo.intersection(o.outer).area > 1
               for o in g.parts if o is not p): continue
        olds = list(p.inner)
        p.outer = Polygon(mo.exterior.coords)
        p.inner = [_mirror(i, cx) for i in olds]
        for f in p.features:
            hit = [k for k, o in enumerate(olds) if f.geom is o]
            f.geom = p.inner[hit[0]] if hit else _mirror(f.geom, cx)
        return g
    return None


FAULTS = [
    Mut('gm01', 'Slots 2 mm narrower than the sheet (drawn for nominal-minus, or for thinner stock)',
        'Mating part cannot be pushed into its slot: sheet goods run at or above nominal thickness, slot joints need '
        'thickness + clearance; a press-fit 2 mm under size splits the ply or will not assemble at all',
        _slot_too_narrow,
        source='Opendesk/WikiHouse slot-joint guidance (slot = measured sheet thickness + fit clearance, measure every '
               'sheet because ply varies); ShopBot "SmartSlots"/press-fit notes; Fab Academy computer-controlled '
               'machining week (press-fit test pieces before cutting furniture)'),
    Mut('gm02', 'Dog-bones missing: rectangular slots/mortises exported with sharp inside corners',
        'A round router bit leaves a tool-radius fillet in every inside corner, so a square tab or the mating sheet '
        'bottoms on the fillets and the joint does not close',
        _no_dogbones,
        source='Opendesk design guidelines (dog-bone/T-bone relief on all internal corners that receive a part); '
               'WikiHouse design guide; Fab Academy CNC week; Fusion 360 "Dogbone" add-in rationale'),
    Mut('gm03', 'Two drilled holes 0.5 mm apart (bores break into each other)',
        'The wall between the bores tears out when drilled or under screw/dowel load; fittings that share the wall '
        '(e.g. cam housing next to a dowel or shelf-pin hole) lose their hold',
        _bores_collide,
        source='Häfele TCH catalogue: Minifix/System 32 drilling patterns keep bores on 32 mm pitch / 24-34 mm '
               'offsets so they never meet; Hettich Ratgeber Möbeltechnik (System 32, Ø5 at 32 mm pitch); '
               'woodworking guidance on minimum screw/dowel spacing in board materials'),
    Mut('gm04', 'Parts nested 1.5 mm apart on the sheet (gap smaller than the cutter)',
        'The router bit is 3-12 mm wide: with a 1.5 mm gap the toolpath around one part cuts into the edge of its '
        'neighbour, and no web is left to hold either part, so both are damaged or thrown',
        _nest_too_tight,
        source='Vectric VCarve/Aspire nesting "Part gap" / "Border gap" (set >= tool diameter so toolpaths do not overlap '
               'neighbouring parts); ShopBot "Holding Down Material for Cutting" (parts need surrounding material/tabs); '
               'Opendesk making guide (leave >= tool diameter + margin between nested parts)'),
    Mut('gm05', 'Round holes exported as coarse 8-sided polygons instead of true circles',
        'Faceted "circles" (SketchUp/Fusion DXF export with coarse arc-to-line tolerance) cut as flat-sided holes: '
        'the inscribed diameter is ~8% under size, so dowels, bolts and cam bolts no longer go in and round parts '
        'come out with visible flats',
        _faceted_holes,
        source='SendCutSend and Ponoko file-prep guides (arcs/circles must be true curves, not segmented polylines); '
               'SketchUp DXF export forum threads (circles exported as 24-segment polygons, low-segment circles cut '
               'as polygons on CNC); Fusion 360 DXF export "splines as polylines" tolerance notes'),
    Mut('gm06', 'Part placed across the stock-sheet border (30 mm of it outside the material)',
        'The part is nested partly off the drawn sheet: the cutter runs in air/spoilboard there, so the part is cut '
        'incomplete (a missing edge) and often hits the clamps/screws that sit in the sheet margin',
        _off_sheet,
        source='ShopBot "Holding Down Material for Cutting" (screws/clamps in the sheet margin; keep toolpaths clear); '
               'Vectric VCarve job setup / nesting "Border gap" (parts must lie inside the material with clearance); '
               'Fab Academy computer-controlled machining week (check the nest against the real sheet before cutting)'),
    Mut('gm07', 'One hole of a regular drilled row (shelf pins / fitting screws / System 32 line) 4 mm off the row line',
        'Shelf-pin and fitting holes must sit on one line at the system pitch: a pin 4 mm off line makes the shelf rock '
        'on three pins (or sit tilted), and a screw hole 4 mm off a runner/hinge-plate pattern misses the fitting\'s '
        'slot, so the hardware cannot be fixed or is forced crooked',
        _row_off_pitch,
        source='Hettich "Ratgeber Möbeltechnik" p5 (System 32: Ø5 holes on one line, 32 mm pitch, 37 mm from the front '
               'edge); Häfele Unitool / line-boring jig instructions (all holes of a row from one reference edge); '
               'Hettich MS 10547 KA 4532 mounting instructions (runner screw holes at 37/165/229 on one screw line); '
               'woodworking forum threads on wobbly shelves from mis-drilled shelf-pin holes'),
    Mut('gm08', 'Part outline crosses itself (figure-8 kink / self-intersecting contour)',
        'CAM cannot decide inside from outside on a self-intersecting vector: VCarve/Aspire and Fusion refuse to offset '
        'it or cut a wrong-side toolpath, so the part is skipped, cut oversize, or gouged where the loop crosses',
        _self_intersect,
        source='Vectric VCarve/Aspire "Validate Vectors" / "Find and fix self-intersections" (self-intersecting '
               'vectors cannot be offset for profile toolpaths); SendCutSend and Ponoko file-preparation guides '
               '(no self-intersecting or overlapping paths); ShopBot/CNCzone forum threads on profile toolpaths failing '
               'from crossed DXF polylines'),
    Mut('gm09', 'Pocketed part drawn mirror-imaged (wrong hand: left side drawn as the right side)',
        'Pockets/rebates are cut from the top face only. A mirrored handed part, flipped to match its outline, has its '
        'housings, rebates and hardware recesses on the wrong face (outside of the cabinet), so the shelves/back/'
        'hardware cannot be fitted - the classic "two left sides" flat-pack error',
        _wrong_hand,
        source='Opendesk making / design guidelines (parts are machined from one face; pockets must face the mating '
               'part, check part orientation before cutting); WikiHouse design guide (handed parts labelled and '
               'oriented on the cutting file); cabinet-software docs (Cabinet Vision / Mozaik "handed / mirrored '
               'parts", left vs right end panels); CNC forum stories of cutting two identical-hand sides'),
]


def _double_contour(g, rng):
    """A part outline exported twice: a second copy 0.5 mm inside the first (stroke-to-path / offset-path export)."""
    from shapely.geometry import JOIN_STYLE
    g = clone(g)
    cand = [p for p in sorted(g.parts, key=lambda q: -q.outer.area)[:12] if p.outer.area > 5000]
    rng.shuffle(cand)
    for p in cand:
        d = p.outer.buffer(-0.5, join_style=JOIN_STYLE.mitre)
        if d.is_empty or d.geom_type != 'Polygon': continue
        d = Polygon(d.exterior.coords)
        if any(not i.within(d) for i in p.inner): continue      # keep the part's own openings inside the copy
        p.inner.append(d)
        return g
    return None


def _construction_line(g, rng):
    """A construction / centre line left on the cut layer, running straight across a part from edge to edge."""
    from shapely.geometry import LineString
    g = clone(g)
    cand = [p for p in sorted(g.parts, key=lambda q: -q.outer.area)[:10] if p.outer.area > 10000]
    rng.shuffle(cand)
    for p in cand:
        r = p.outer.minimum_rotated_rectangle
        if r.geom_type != 'Polygon': continue
        c = list(r.exterior.coords)
        a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
        (x0, y0), (x1, y1) = (c[0], c[1]) if a < b else (c[1], c[2])    # short side: the line runs across the part
        ux, uy = (x1 - x0) / min(a, b), (y1 - y0) / min(a, b)
        m = p.outer.centroid
        if not p.outer.contains(m): continue
        h = min(a, b) / 2 + 20
        line = LineString([(m.x - ux * h, m.y - uy * h), (m.x + ux * h, m.y + uy * h)])
        if any(line.intersects(o.outer) for o in g.parts if o is not p): continue
        g.open_chains.append((line, p.layer))
        return g
    return None


def _hole_under_layer_tool(g, rng):
    """Holes on a layer that names the drill size (Opendesk 'HOLE-6.000MM-DIAM') drawn 2 mm smaller than that size:
    the circle was resized for a smaller fastener but left on the old tool's layer."""
    from fc.gx.model import layer_op
    g = clone(g)
    cand = []
    for p in g.parts:
        for f in p.features:
            if f.op == 'hole' and f.r and f.geom is not None:
                dia = layer_op(f.layer)[2]
                if dia and dia >= 5 and abs(2 * f.r - dia) < 0.1:
                    cand.append((p, f, dia))
    if not cand: return None
    p0 = rng.choice(cand)[0]
    n = 0
    for p, f, dia in cand:
        if p is not p0: continue
        c = f.geom.centroid
        nr = (dia - 2.0) / 2
        m = Point(c.x, c.y).buffer(nr, 32)
        if f.geom in p.inner: p.inner[p.inner.index(f.geom)] = m
        f.geom = m; f.r = nr; n += 1
    return g if n else None


FAULTS += [
    Mut('gm30', 'Part outline exported twice: a second contour 0.5 mm inside the first (double line)',
        'CAM sees two closed vectors and cuts both: the outer profile frees the part, the inner one (read as an '
        'opening) cuts a 0.5 mm ring off it - the part comes out a cutter width undersize, the sliver is thrown, and '
        'every joint on that part is loose; on a nested sheet the two toolpaths also double the cutting time',
        _double_contour,
        source='SendCutSend and Ponoko file-preparation guides (no double / duplicate or overlapping lines; outlined '
               'strokes - "stroke to path" - export as two contours); Vectric VCarve "Find duplicate vectors" / '
               '"Join vectors" tools; Inkscape and Illustrator DXF-for-CNC export notes (convert strokes to a single '
               'path, not an outline of the stroke)'),
    Mut('gm31', 'Construction / centre line left on the cut layer, running across a part from edge to edge',
        'Everything on a through-cut layer is machined: a reference line drawn across a part is cut through the '
        'full sheet thickness and splits the part in two (or leaves a deep kerf across it) - the part is scrap',
        _construction_line,
        source='SendCutSend file guidelines (remove construction lines, dimensions and anything that is not a cut '
               'path); Opendesk design guidelines (only toolpath geometry on the CUT layers, everything else on '
               'non-cutting layers); Vectric / ShopBot forum threads on parts cut in half by stray lines left in the DXF'),
    Mut('gm32', 'Holes drawn 2 mm smaller than the drill size named on their layer (HOLE-xMM-DIAM)',
        'Layer-driven CAM (Opendesk convention: TOP-HOLE-<tool>MM-DIAM_<depth>MM) picks the drill from the layer '
        'name, not the circle: a hole resized for a smaller fastener but left on the old layer is drilled at the '
        'layer size, 2 mm oversize - screws and dowels have nothing to bite and the joint falls apart',
        _hole_under_layer_tool,
        source='Opendesk "Making" / CAM layer conventions (tool and depth encoded in the layer name, e.g. '
               'TOP-HOLE-6.000MM-DIAM_14.000MM); Vectric "toolpath templates" and Fusion 360 layer-based drilling '
               '(operations are applied per layer); Häfele TCH dowel and screw pilot sizes (Ø8 dowel in Ø8, '
               'Ø5 screw pilot for Ø7 Confirmat)'),
]


def _edge_slit(g, rng):
    """A 2 mm wide, 30 mm deep slit drawn into a part edge (a saw-kerf relief / kerf-bend cut drawn for a blade)."""
    g = clone(g)
    cand = [p for p in sorted(g.parts, key=lambda q: -q.outer.area)[:10] if p.outer.area > 20000]
    rng.shuffle(cand)
    for p in cand:
        pts = list(p.outer.exterior.coords)
        segs = [i for i in range(len(pts) - 1) if math.dist(pts[i], pts[i + 1]) > 80]
        if not segs: continue
        i = rng.choice(segs)
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        L = math.dist(pts[i], pts[i + 1]); tx, ty = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = (-ty, tx) if p.outer.exterior.is_ccw else (ty, -tx)        # inward normal
        mx, my = x0 + tx * L / 2, y0 + ty * L / 2
        P = lambda a, b: (mx + tx * a + nx * b, my + ty * a + ny * b)
        slit = Polygon([P(-1, -2), P(1, -2), P(1, 30), P(-1, 30)])
        if not slit.intersects(p.outer) or slit.intersection(p.outer).area < 50: continue
        if any(slit.buffer(3).intersects(o) for o in p.inner) or any(slit.buffer(3).intersects(f.geom) for f in p.features):
            continue
        new = p.outer.difference(slit)
        if new.is_empty or new.geom_type != 'Polygon' or abs(new.area - (p.outer.area - 60)) > 15: continue
        p.outer = Polygon(new.exterior.coords)
        return g
    return None


def _no_sheet_margin(g, rng):
    """A part nested 1 mm from the edge of the drawn stock sheet (no margin for the sheet's rough edge / clamps)."""
    if g.sheet is None: return None
    g = clone(g); sb = g.sheet.exterior
    cand = [p for p in g.parts if p.outer.within(g.sheet) and p.outer.area > 2000 and sb.distance(p.outer) > 5]
    rng.shuffle(cand)
    for p in cand:
        pa, pb = nearest_points(p.outer.exterior, sb)
        d = pa.distance(pb)
        k = (d - 1.0) / d
        dx, dy = (pb.x - pa.x) * k, (pb.y - pa.y) * k
        moved = affinity.translate(p.outer, dx, dy)
        if not moved.within(g.sheet): continue
        if any(moved.distance(o.outer) < 5 for o in g.parts if o is not p): continue
        _translate_part(p, dx, dy)
        return g
    return None


def _openings_thin_web(g, rng):
    """One through opening moved toward its nearest neighbouring opening so only 1 mm of sheet is left between them."""
    g = clone(g)
    cand = []
    for p in g.parts:
        ii = [i for i in p.inner if i.area > 50]
        if len(ii) < 2 or len(ii) > 200: continue
        for i in ii:
            others = [o for o in ii if o is not i]
            j = min(others, key=lambda o: o.distance(i))
            if i.distance(j) > 6: cand.append((p, i, j))
    rng.shuffle(cand)
    for p, i, j in cand:
        a, b = nearest_points(i, j)
        d = a.distance(b)
        k = (d - 1.0) / d
        m = affinity.translate(i, (b.x - a.x) * k, (b.y - a.y) * k)
        if not m.within(p.outer) or p.outer.exterior.distance(m) < 5: continue
        if any(m.distance(o) < 0.9 for o in p.inner if o is not i): continue
        if any(m.intersects(f.geom) for f in p.features if f.geom is not i): continue
        _replace_inner(p, i, m)
        return g
    return None


FAULTS += [
    Mut('gm33', 'A 2 mm wide slit drawn into a part edge (saw-kerf relief / kerf-bend line drawn for a blade)',
        'A router cannot cut an opening narrower than its bit: the smallest bit that cuts through furniture sheet is '
        '1/8" (3.175 mm). CAM either skips the slit (the relief / bend cut is missing and the part will not flex or '
        'fit) or plunges a bit too big for it, cutting it 1+ mm oversize, and thinner bits snap in sheet that deep',
        _edge_slit,
        source='Amana compression bit range (smallest through-cutting bit 1/8", 46180: 20.6 mm cut length); Vectric '
               'VCarve profile/pocket toolpaths ("tool too large for the vector": no toolpath is generated); '
               'Fab Academy computer-controlled machining week (design for the bit: no features under the tool '
               'diameter); kerf-bending guides (slits drawn for laser / saw kerf, not router)'),
    Mut('gm34', 'Part nested 1 mm from the edge of the drawn stock sheet (no edge margin)',
        'Factory sheet edges are not square, are often dented or chipped, and are where the clamps / screws hold the '
        'sheet: a part 1 mm from the border gets a damaged or short edge, or the cutter runs into the hold-down',
        _no_sheet_margin,
        source='ShopBot "Holding Down Material for Cutting" (screws / clamps along the sheet margin, keep toolpaths '
               'clear); Vectric nesting "Border gap" (default margin to the material edge); Opendesk making guide '
               '(keep a margin round the sheet for hold-down and edge damage)'),
    Mut('gm35', 'Two through openings only 1 mm apart (sheet web between two slots / cut-outs)',
        'The bridge of sheet between two neighbouring openings must survive both profile cuts and the load in use: '
        '1 mm of ply or MDF is crushed by the cutter, breaks out when the second opening is cut, or snaps as soon as '
        'the parts in the slots are loaded - the two slots become one and both joints go loose',
        _openings_thin_web,
        source='Opendesk design guidelines (minimum material between features / slots, about the sheet thickness); '
               'WikiHouse design guide (minimum web between adjacent slots); Fab Academy CNC week press-fit notes '
               '(thin bridges between slots break during cutting); ShopBot forum threads on webs snapping between '
               'closely spaced slots'),
]
