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



def _slot_too_wide(g, rng):
    """Slots drawn 3 mm wider than the sheet (drawn for thicker stock, or clearance added twice)."""
    if not g.thickness: return None
    g = clone(g); th = g.thickness; n = 0
    for p in g.parts:
        for i, w, ang in _slots(p, th):
            c = i.centroid
            m = affinity.rotate(i, -ang, origin=c)
            m = affinity.scale(m, 1.0, (th + 3.0) / w, origin=c)
            m = affinity.rotate(m, ang, origin=c)
            if not m.is_valid or m.is_empty or not m.within(p.outer) or p.outer.exterior.distance(m) < 3: continue
            if any(m.intersects(o) for o in p.inner if o is not i): continue
            _replace_inner(p, i, m); n += 1
    return g if n else None


def _thin_neck(g, rng):
    """A notch cut into the edge of a big part leaves only a 6 mm neck of material across the part."""
    from shapely.geometry import LineString
    g = clone(g); neck = 6.0
    cand = [p for p in g.parts if p.outer.area > 20000 and p.outer.is_valid]
    rng.shuffle(cand)
    for p in cand[:8]:
        ring = p.outer.exterior
        pts = list(ring.coords)[:-1]
        edges = [(k, math.dist(pts[k], pts[(k + 1) % len(pts)])) for k in range(len(pts))]
        edges = [e for e in edges if e[1] > 80]
        rng.shuffle(edges)
        for k, L in edges[:6]:
            (x0, y0), (x1, y1) = pts[k], pts[(k + 1) % len(pts)]
            tx, ty = (x1 - x0) / L, (y1 - y0) / L
            nx, ny = (-ty, tx) if ring.is_ccw else (ty, -tx)          # inward normal
            mx, my = x0 + tx * L / 2, y0 + ty * L / 2
            ray = LineString([(mx + nx * 0.01, my + ny * 0.01), (mx + nx * 2000, my + ny * 2000)])
            hit = ray.intersection(p.poly.boundary)
            if hit.is_empty: continue
            pts_hit = [hit] if hit.geom_type == 'Point' else [q for q in getattr(hit, 'geoms', []) if q.geom_type == 'Point']
            if not pts_hit: continue
            W = min(Point(mx, my).distance(q) for q in pts_hit)
            if not 40 <= W <= 400: continue
            d = W - neck; hw = 10.0
            P = lambda a, b: (mx + tx * a + nx * b, my + ty * a + ny * b)
            notch = Polygon([P(-hw, -1), P(hw, -1), P(hw, d), P(-hw, d)])
            if any(notch.intersects(o) for o in p.inner): continue
            new = p.outer.difference(notch)
            if new.geom_type != 'Polygon' or new.is_empty: continue
            if new.area < p.outer.area - 2 * hw * d - 50: continue
            p.outer = Polygon(new.exterior.coords)
            return g
    return None


def _letter(x, y, ch, h=8.0, s=1.2):
    """Single-stroke capital as a closed outline (stroke width s, height h) at (x, y) - what exploded text looks like."""
    w = 0.6 * h
    shapes = {
        'I': [(0, 0), (s, 0), (s, h), (0, h)],
        'L': [(0, 0), (w, 0), (w, s), (s, s), (s, h), (0, h)],
        'T': [(w / 2 - s / 2, 0), (w / 2 + s / 2, 0), (w / 2 + s / 2, h - s), (w, h - s), (w, h), (0, h), (0, h - s),
              (w / 2 - s / 2, h - s)],
        'E': [(0, 0), (w, 0), (w, s), (s, s), (s, h / 2 - s / 2), (w * 0.8, h / 2 - s / 2), (w * 0.8, h / 2 + s / 2),
              (s, h / 2 + s / 2), (s, h - s), (w, h - s), (w, h), (0, h)],
        'F': [(0, 0), (s, 0), (s, h / 2 - s / 2), (w * 0.8, h / 2 - s / 2), (w * 0.8, h / 2 + s / 2), (s, h / 2 + s / 2),
              (s, h - s), (w, h - s), (w, h), (0, h)],
    }
    return Polygon([(x + a, y + b) for a, b in shapes[ch]])


def _text_on_cut(g, rng):
    """A part label ('LEFT', 'FEET'...) exploded to outlines and left on the cut layer: the letters are cut through."""
    g = clone(g)
    cand = [p for p in g.parts if p.outer.area > 30000 and p.outer.is_valid]
    rng.shuffle(cand)
    word = rng.choice(['LEFT', 'FEET', 'TILE', 'LIFT'])
    for p in cand:
        c = p.outer.representative_point() if not p.outer.centroid.within(p.outer) else p.outer.centroid
        for dx, dy in ((0, 0), (40, 0), (-40, 0), (0, 40), (0, -40)):
            x0, y0 = c.x + dx - 14, c.y + dy - 4
            letters = [_letter(x0 + 7.5 * k, y0, ch) for k, ch in enumerate(word)]
            box = Polygon([(x0 - 6, y0 - 6), (x0 + 36, y0 - 6), (x0 + 36, y0 + 14), (x0 - 6, y0 + 14)])
            if not box.within(p.outer) or p.outer.exterior.distance(box) < 5: continue
            if any(box.intersects(o) for o in p.inner) or any(box.intersects(f.geom) for f in p.features): continue
            p.inner.extend(letters)
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
    Mut('gm20', 'Slots 3 mm wider than the sheet (drawn for thicker stock, or fit clearance added twice)',
        'A slot joint holds only by its fit: Opendesk/WikiHouse press-fit slots are sheet + 0.1-0.5 mm. With 3 mm of '
        'play the joint rattles and racks, the frame is not square, and the parts fall apart under sideways load '
        '(wedges or glue cannot fill a 3 mm gap)',
        _slot_too_wide,
        source='Opendesk design guidelines (slot = measured sheet thickness + small clearance; test the fit first); '
               'WikiHouse design guide (tight friction joints are what make the frame rigid); ShopBot/Fab Academy '
               'press-fit test-piece practice; CNC forum threads on wobbly slot furniture cut for 3/4" nominal from '
               '18 mm (23/32") ply'),
    Mut('gm21', 'Notch leaves a 6 mm neck across a part (part almost cut in two)',
        'Plywood/MDF across a 6 mm neck has a fraction of the part\'s strength: it snaps while being cut (the part '
        'is held only there and the cutter pushes it), or at the first load; in ply the neck can be pure short grain',
        _thin_neck,
        source='Opendesk design guidelines (minimum feature width roughly the sheet thickness / bit diameter; avoid '
               'narrow necks and short grain); WikiHouse design guide (no thin necks in structural parts); ShopBot '
               '"Holding Down Material for Cutting" (narrow features vibrate and break during cutting)'),
    Mut('gm22', 'Part label left on the cut layer: exploded lettering is cut through the part',
        'Labels must go on an engrave / mark layer. On a through-cut layer the CAM cuts every letter out (holes in a '
        'visible face, letter strokes ~1 mm wide that no router bit fits, loose letter pieces thrown by the cutter)',
        _text_on_cut,
        source='Ponoko and SendCutSend file-preparation guides (text must be converted and placed on an engrave '
               'layer/colour, never on the cut layer); Opendesk cutting-file layer conventions (labels on a '
               'separate non-cut layer); Fab Academy CNC week notes on layer set-up in VCarve/Fusion'),
]
