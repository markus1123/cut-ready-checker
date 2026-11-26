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


# ---- shard a, round 1 ----------------------------------------------------------------------------------------------

def _glyphs(x0, y0, h, s):
    """Outlines of the letters 'L', 'T', 'I', 'E' (h mm tall, stroke s mm) as closed polygons starting at x0, y0."""
    w = 0.6 * h
    L = Polygon([(0, 0), (w, 0), (w, s), (s, s), (s, h), (0, h)])
    T = Polygon([(0, h - s), (w, h - s), (w, h), (0, h)]).union(Polygon([(w / 2 - s / 2, 0), (w / 2 + s / 2, 0), (w / 2 + s / 2, h), (w / 2 - s / 2, h)]))
    I = Polygon([(0, 0), (s, 0), (s, h), (0, h)])
    E = Polygon([(0, 0), (w, 0), (w, s), (s, s), (s, h / 2 - s / 2), (0.8 * w, h / 2 - s / 2), (0.8 * w, h / 2 + s / 2),
                 (s, h / 2 + s / 2), (s, h - s), (w, h - s), (w, h), (0, h)])
    out, x = [], x0
    for gl, gw in ((L, w), (T, w), (I, s), (E, w)):
        out.append(affinity.translate(Polygon(gl.exterior.coords), x, y0)); x += gw + 0.5 * h
    return out


def _label_on_cut(g, rng):
    """A part label ('LTIE', 12 mm letters, 1.5 mm strokes) drawn on the through-cut layer instead of an engrave layer."""
    g = clone(g)
    cand = [p for p in sorted(g.parts, key=lambda q: -q.outer.area)[:8] if p.outer.area > 20000]
    rng.shuffle(cand)
    h, s = 12.0, 1.5
    for p in cand:
        poly = p.poly
        for _ in range(40):
            minx, miny, maxx, maxy = p.outer.bounds
            x0 = rng.uniform(minx, maxx - 4 * h); y0 = rng.uniform(miny, maxy - h)
            gl = _glyphs(x0, y0, h, s)
            box = Polygon([(x0 - 5, y0 - 5), (x0 + 3.6 * h + 5, y0 - 5), (x0 + 3.6 * h + 5, y0 + h + 5), (x0 - 5, y0 + h + 5)])
            if not box.within(poly) or any(box.intersects(f.geom) for f in p.features):
                continue
            p.inner.extend(gl)
            return g
    return None


def _slot_skewed(g, rng):
    """One slot for a mating sheet drawn rotated 4 degrees off square (snap/rotate error in CAD)."""
    if not g.thickness: return None
    g = clone(g)
    cand = [(p, i) for p in g.parts for i, w, ang in _slots(p, g.thickness)]
    rng.shuffle(cand)
    for p, i in cand:
        m = affinity.rotate(i, rng.choice((4.0, -4.0)), origin=i.centroid)
        if not m.within(p.outer) or p.outer.exterior.distance(m) < 1.0: continue
        if any(m.intersects(o) for o in p.inner if o is not i): continue
        _replace_inner(p, i, m)
        return g
    return None


def _congruent(a, b):
    if abs(a.outer.area - b.outer.area) > 0.005 * a.outer.area: return False
    ca, cb = a.outer.centroid, b.outer.centroid
    ob = affinity.translate(b.outer, ca.x - cb.x, ca.y - cb.y)
    for ang in (0, 90, 180, 270):
        if affinity.rotate(ob, ang, origin=ca).symmetric_difference(a.outer).area < 0.005 * a.outer.area:
            return True
    return False


def _hole_dropped(g, rng):
    """One drilled hole missing from one of two (or more) identical parts: its twin still has it (layer/block lost on export)."""
    g = clone(g)
    cand = []
    big = [p for p in g.parts if p.outer.area > 5000 and holes(p)]
    for a in big:
        for b in big:
            if a is not b and len(holes(a)) == len(holes(b)) and _congruent(a, b):
                cand.append(a); break
    rng.shuffle(cand)
    for p in cand:
        f = rng.choice(holes(p))
        p.features.remove(f)
        if f.geom in p.inner: p.inner.remove(f.geom)
        return g
    return None


FAULTS += [
    Mut('gm10', 'Part label / number drawn on the through-cut layer (letters cut out of the part)',
        'Text meant to be engraved or marked is exported onto the profile-cut layer: the router cuts each letter '
        'through the sheet, leaving holes in a visible face, loose letter slugs that the cutter throws, and 1.5 mm '
        'letter strokes that no furniture bit can follow',
        _label_on_cut,
        source='SendCutSend and Ponoko file-preparation guides (text must be on an engrave/mark layer or converted '
               'deliberately; text on the cut layer is cut out); Vectric VCarve/Aspire (labels go to an engraving or '
               'V-carve toolpath, not a profile); Fab Academy CNC week reports of part numbers cut through by mistake'),
    Mut('gm11', 'A sheet slot drawn 4 degrees off square (rotated by a snap / rotate error)',
        'The mating sheet enters a skewed slot at an angle: 4 degrees over an 18 mm thick sheet is about 1.3 mm of '
        'misalignment across the slot, so a press-fit joint binds or splits the ply, and the assembled part leans',
        _slot_skewed,
        source='Opendesk / WikiHouse slot-joint design guidance (slots square to the mating sheet, cut to sheet '
               'thickness + clearance); Fab Academy press-fit assignments (joints bind when slots are not aligned); '
               'CAD forum threads on rotation snap / "angle off by a degree" errors in DXF exports'),
    Mut('gm12', 'One drilled hole missing on one of two identical parts (its twin still has it)',
        'Identical parts are drilled for the same hardware; when a hole is lost on export (hidden/frozen layer, '
        'exploded block) one copy is cut without it, so a screw, dowel, cam or shelf pin has nowhere to go and the '
        'part has to be drilled by hand or recut',
        _hole_dropped,
        source='Hettich/Häfele mounting instructions (each panel of a pair carries the same System 32 / fitting '
               'bores); Opendesk making guide (check the file against the assembly drawing - every hole must be '
               'present); CNC forum stories of holes missing after DXF export from hidden or frozen layers'),
]


# ---- shard a, round 2 ----------------------------------------------------------------------------------------------

def _opening_doubled(g, rng):
    """A slot / cut-out drawn twice, the copy shifted 1.2 mm sideways (duplicate geometry left after an edit)."""
    if not g.thickness: return None
    g = clone(g)
    cand = [(p, i, w, ang) for p in g.parts for i, w, ang in _slots(p, g.thickness)]
    rng.shuffle(cand)
    for p, i, w, ang in cand:
        a = math.radians(ang + 90.0)                          # across the slot
        s = rng.choice((1.2, -1.2))
        m = affinity.translate(i, s * math.cos(a), s * math.sin(a))
        if not m.within(p.outer) or p.outer.exterior.distance(m) < 2.0: continue
        if any(m.intersects(o) for o in p.inner if o is not i): continue
        p.inner.append(m)
        return g
    return None


def _outline_lost(g, rng):
    """One part's outline lost on export (hidden / frozen layer): only its openings are left in the file, as loose loops."""
    from fc.gx.model import Part
    g = clone(g)
    cand = [p for p in g.parts if len([i for i in p.inner if i.area > 100]) >= 2 and p.outer.area > 20000]
    rng.shuffle(cand)
    for p in cand:
        g.parts.remove(p)
        for i in p.inner:
            if i.area > 100:
                g.parts.append(Part(outer=Polygon(i.exterior.coords), layer=p.layer, depth=p.depth))
        return g
    return None


def _edge_slots(p, th):
    """Open slots in the outline (cross-halving / slot-together notches) ~ sheet thickness wide: (notch polygon, w, L, ang)."""
    o = Polygon(p.outer.exterior.coords)
    if not o.is_valid: return []
    hull = o.buffer(30, join_style=2).buffer(-30, join_style=2)
    d = hull.difference(o)
    out = []
    for x in getattr(d, 'geoms', [d]):
        if x.is_empty or x.geom_type != 'Polygon' or x.area < 50: continue
        r, w, L, ang = _rect_axes(x)
        if 0.95 * th <= w <= 1.3 * th and L >= 2 * w and x.area > 0.8 * r.area:
            out.append((x, w, L, ang))
    return out


def _notch_shallow(g, rng):
    """One slot-together edge notch cut only 60 % as deep as drawn (half-lap notch shortened)."""
    if not g.thickness: return None
    g = clone(g)
    cand = [(p, n, w, L, ang) for p in g.parts for n, w, L, ang in _edge_slots(p, g.thickness)]
    rng.shuffle(cand)
    for p, n, w, L, ang in cand:
        cut = L * 0.4                                         # material put back at the bottom of the notch
        o = Polygon(p.outer.exterior.coords)
        mouth = n.exterior.intersection(o.exterior.buffer(0.05))
        if mouth.is_empty: continue
        mc = mouth.centroid
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)
        c = n.centroid
        if (c.x - mc.x) * ux + (c.y - mc.y) * uy < 0: ux, uy = -ux, -uy      # unit vector mouth -> bottom
        far = max(((x - mc.x) * ux + (y - mc.y) * uy) for x, y in n.exterior.coords)
        bx, by = mc.x + ux * (far - cut), mc.y + uy * (far - cut)
        nx, ny = -uy, ux
        big = 4 * w
        fill = Polygon([(bx + nx * big, by + ny * big), (bx - nx * big, by - ny * big),
                        (bx - nx * big + ux * L, by - ny * big + uy * L), (bx + nx * big + ux * L, by + ny * big + uy * L)])
        add = n.intersection(fill)
        if add.is_empty or add.area < 0.2 * n.area: continue
        new = o.union(add.buffer(0.01, join_style=2))
        if new.geom_type != 'Polygon' or len(new.interiors): continue
        p.outer = Polygon(new.exterior.coords)
        return g
    return None


FAULTS += [
    Mut('gm13', 'A slot drawn twice, the copy 1.2 mm to one side (duplicate geometry after an edit)',
        'CAM cuts both loops: the slot comes out 1.2 mm wider than drawn, so the press-fit joint is loose and racks, '
        'and the toolpath runs twice along the same edge leaving a sliver that burns or breaks off',
        _opening_doubled,
        source='Vectric VCarve/Aspire "Delete duplicate vectors" / "Join open vectors" file-clean-up step before '
               'toolpathing; SendCutSend and Ponoko file guides (no duplicate or overlapping lines); ShopBot forum '
               'threads on double cuts from duplicated DXF entities'),
    Mut('gm14', 'A part\'s outline missing from the file (only its openings are left, as loose loops)',
        'The outline was on a hidden / frozen / non-cut layer at export: the router cuts the slots and holes as '
        'loose slugs and never cuts the part out, so one part of the kit is missing and the slugs are thrown',
        _outline_lost,
        source='Vectric / Fusion 360 DXF export notes (only visible layers and selected geometry are exported); '
               'Opendesk making guide (check the cut file against the parts list before cutting); CNC forum stories '
               'of parts missing from a DXF because their layer was frozen or off'),
    Mut('gm15', 'Slot-together edge notch cut only 60 % as deep as drawn for the joint',
        'A cross-halving / slot-together joint needs the two notches to add up to the full part width: a notch '
        'shortened by 40 % stops the parts before they are flush, so the top edges do not line up, the joint '
        'is not seated and the furniture rocks',
        _notch_shallow,
        source='Opendesk / AtFAB slot-together joint libraries (Digital Wood Joints: cross-lap notch depth = half the '
               'mating part height); WikiHouse design guide (joints must seat fully); Fab Academy press-fit '
               'assignments (notch depth errors leave parts proud)'),
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


# ---- shard f, round 2 ----------------------------------------------------------------------------------------------

def _f_outline_inside(g, rng):
    """A part's outline put on the INSIDE-cut layer (Opendesk TOP-CUT-OUTSIDE -> TOP-CUT-INSIDE): the profile side is
    swapped, so CAM offsets the cutter into the part instead of away from it."""
    import re
    g = clone(g)
    cand = [p for p in g.parts if re.search(r'(?i)OUTSIDE', p.layer or '') and p.outer.area > 5000]
    if not cand: return None
    p = rng.choice(cand)
    p.layer = re.sub(r'(?i)OUTSIDE', 'INSIDE', p.layer)
    return g


def _f_thin_floor(g, rng):
    """All pockets of one part cut to sheet thickness minus 1 mm (depth taken from the wrong, thinner, stock or
    from a through-cut template): a 1 mm floor of face veneer is left under each pocket."""
    if not g.thickness: return None
    g = clone(g); th = g.thickness
    cand = [p for p in g.parts if any(f.op == 'pocket' and f.depth and f.depth < th - 2.0 for f in p.features)]
    if not cand: return None
    p = rng.choice(cand)
    for f in p.features:
        if f.op == 'pocket' and f.depth and f.depth < th - 2.0:
            f.depth = th - 1.0
    return g


def _f_openings_left_behind(g, rng):
    """One of two identical parts moved without its openings (holes / slots on a locked or hidden layer stay put):
    all its openings and holes end up 8 mm off, relative to its outline, while the twin part is right."""
    g = clone(g)
    big = [p for p in g.parts if p.outer.area > 10000 and len([i for i in p.inner if i.area > 20]) >= 2]
    pairs = [a for a in big for b in big if a is not b and _congruent(a, b)]
    rng.shuffle(pairs)
    for p in pairs:
        for dx, dy in rng.sample([(8, 0), (-8, 0), (0, 8), (0, -8)], 4):
            moved = [affinity.translate(i, dx, dy) for i in p.inner]
            if not all(m.within(p.outer) and p.outer.exterior.distance(m) >= 2.0 for m in moved): continue
            ok = True
            for f in p.features:
                if f.op != 'hole' and not any(f.geom is i for i in p.inner):
                    if not affinity.translate(f.geom, dx, dy).within(p.outer): ok = False
            if not ok: continue
            old = list(p.inner)
            p.inner = moved
            for f in p.features:
                k = [j for j, i in enumerate(old) if f.geom is i]
                f.geom = moved[k[0]] if k else affinity.translate(f.geom, dx, dy)
            return g
    return None


FAULTS += [
    Mut('gm40', 'A part outline on the INSIDE-cut layer (profile side swapped: CUT-OUTSIDE -> CUT-INSIDE)',
        'Layer-driven CAM offsets the cutter by the layer: an outline on the inside-profile layer is cut with the '
        'tool inside the line, so the part comes out one bit diameter (6-12 mm) undersize all round - every tab, '
        'slot position and edge distance on it is wrong and it does not fit its neighbours',
        _f_outline_inside,
        source='Opendesk CAM layer convention (TOP-CUT-OUTSIDE for part profiles, TOP-CUT-INSIDE for openings; tool '
               'side taken from the layer); Vectric VCarve/Aspire profile toolpath "Machine Vectors: Outside / Inside" '
               'and toolpath templates per layer; ShopBot / Vectric forum threads on parts cut a bit-width undersize '
               'because the profile was set to inside'),
    Mut('gm41', 'Pockets of one part cut to sheet thickness minus 1 mm (a 1 mm floor left under each pocket)',
        'A 1 mm floor is only the face veneer: it tears out or breaks through under the cutter, the part loses '
        'vacuum hold as the floor flexes, and in use the hardware / mating part pushes straight through it',
        _f_thin_floor,
        source='Vectric / ShopBot pocketing guidance (leave enough floor; thin floors flex and break through, '
               'especially on vacuum tables); Häfele Minifix housing depths (13.5-14.5 mm in 18-19 mm board, leaving '
               '4.5-5 mm); Opendesk pocket depths (9 mm in 18 mm, half the sheet); EN 315 ply thickness tolerance '
               '(+/-0.74 mm at 18 mm, so a 1 mm planned floor can be 0.3 mm or a hole)'),
    Mut('gm42', 'One of two identical parts moved without its openings: all its holes and slots 8 mm off',
        'Holes and slots on a locked / hidden / separate layer do not move when the outline is nested or moved: '
        'the part is cut with every opening 8 mm out of place, so screws, dowels and the mating parts in its slots '
        'do not line up with the other parts (its twin is right, so the assembly will not go together)',
        _f_openings_left_behind,
        source='Vectric VCarve / Aspire nesting and layer locking (locked or hidden layers are not moved with the '
               'selection); SketchUp / Inkscape group-vs-loose-geometry export threads; CNC forum stories of holes '
               'cut in the old position after a part was moved for nesting; Opendesk making guide (check the file '
               'against the assembly drawing before cutting)'),
]
