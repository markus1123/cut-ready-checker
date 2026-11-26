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


def _f_outline_spur(g, rng):
    """A zero-width spur on a part outline: a 0.3 mm wide, 15 mm long spike sticking out of a straight edge, left by
    a failed offset / fillet / join in CAD (the contour runs out to a point and back)."""
    g = clone(g)
    cand = [p for p in sorted(g.parts, key=lambda q: -q.outer.area)[:10] if p.outer.area > 20000]
    rng.shuffle(cand)
    for p in cand:
        pts = list(p.outer.exterior.coords)
        segs = [i for i in range(len(pts) - 1) if math.dist(pts[i], pts[i + 1]) > 60]
        if not segs: continue
        i = rng.choice(segs)
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        L = math.dist(pts[i], pts[i + 1]); tx, ty = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = (ty, -tx) if p.outer.exterior.is_ccw else (-ty, tx)        # outward normal
        mx, my = x0 + tx * L / 2, y0 + ty * L / 2
        P = lambda a, b: (mx + tx * a + nx * b, my + ty * a + ny * b)
        spur = Polygon([P(-0.15, -0.5), P(0.15, -0.5), P(0.15, 15), P(-0.15, 15)])
        if any(spur.buffer(5).intersects(o.outer) for o in g.parts if o is not p): continue
        if g.sheet is not None and not spur.within(g.sheet): continue
        new = p.outer.union(spur)
        if new.is_empty or new.geom_type != 'Polygon' or len(new.interiors): continue
        p.outer = Polygon(new.exterior.coords)
        return g
    return None


def _f_dpi_scale(g, rng):
    """The whole drawing scaled by 96/72 = 1.333: an SVG / PDF drawn in 72 dpi points read as 96 dpi pixels (or the
    reverse) on the way to DXF - every part, slot and hole one third too big."""
    g = clone(g); k = 96.0 / 72.0
    for p in g.parts:
        p.outer = affinity.scale(p.outer, k, k, origin=(0, 0)); p.inner = [affinity.scale(i, k, k, origin=(0, 0)) for i in p.inner]
        for f in p.features:
            f.geom = affinity.scale(f.geom, k, k, origin=(0, 0)); f.r = f.r * k if f.r else f.r
    g.open_chains = [(affinity.scale(l, k, k, origin=(0, 0)), lay) for l, lay in g.open_chains]
    if g.sheet is not None: g.sheet = affinity.scale(g.sheet, k, k, origin=(0, 0))
    return g


def _f_profile_short(g, rng):
    """One part's profile layer depth set 3 mm short of the sheet (TOP-CUT-OUTSIDE_18 -> _15): the part is not cut free."""
    import re
    if not g.thickness or g.thickness < 6: return None
    g = clone(g); th = g.thickness
    cand = [p for p in g.parts if p.depth and abs(p.depth - th) < 0.05 and re.search(r'_(\d+(?:\.\d+)?)\s*MM\s*$', (p.layer or '').upper())
            and p.outer.area > 5000]
    if not cand: return None
    p = rng.choice(cand)
    d = th - 3.0
    p.depth = d
    p.layer = re.sub(r'(?i)_(\d+(?:\.\d+)?)(\s*MM\s*)$', lambda m: '_%.3f%s' % (d, m.group(2)), p.layer)
    return g


FAULTS += [
    Mut('gm43', 'A zero-width spur on a part outline (0.3 mm wide, 15 mm long spike from a failed offset / join)',
        'The outline runs out to a point and back: the cutter cannot enter a 0.3 mm gap, so the spur is left as a '
        'paper-thin fin of sheet sticking out of the edge (it splinters off, leaves a ragged edge and stops the edge '
        'sitting flush against its neighbour), or CAM rejects / mangles the self-touching contour',
        _f_outline_spur,
        source='Vectric VCarve "Find duplicate / overlapping vectors" and node-editing clean-up of offset artefacts; '
               'Fusion 360 / Inkscape "offset path" and "stroke to path" artefacts (spikes at sharp corners); '
               'SendCutSend file guidelines (no zero-width features, features at least the material thickness / '
               'tool size); ShopBot forum threads on spikes in imported DXF outlines'),
    Mut('gm44', 'Whole drawing 1.333x too large (72 dpi points read as 96 dpi pixels on SVG / PDF -> DXF)',
        'Every part, slot and hole is one third too big: 18 mm slots come out 24 mm and rattle, 8 mm dowel holes come '
        'out 10.7 mm, and parts may not fit the sheet - the whole cut is scrap',
        _f_dpi_scale,
        source='Inkscape 0.92 release notes (user unit changed 90 -> 96 dpi; files scale on import); Adobe Illustrator '
               'DXF export (72 pt per inch artboard units); laser / CNC forum threads on parts cut 1.25x / 1.33x / '
               '0.75x size after SVG -> DXF; SendCutSend "check your scale" upload guidance'),
    Mut('gm45', 'One part\'s profile cut depth 3 mm short of the sheet (cut layer _18MM -> _15MM): not cut free',
        'The profile stops 3 mm above the spoilboard: the part stays attached to the sheet by a 3 mm skin all round. '
        'Onion skins are 0.25-0.76 mm; 3 mm cannot be snapped or trimmed off - the part is torn out with ragged, '
        'splintered edges, or has to be recut',
        _f_profile_short,
        source='ShopBot "Holding Down Material for Cutting" p8 (onion skin 0.010-0.030 in = 0.25-0.76 mm); Opendesk '
               'CAM layer convention (cut depth in the layer name, TOP-CUT-OUTSIDE_18.000MM = through the 18 mm '
               'sheet); Vectric toolpath templates (cut depth taken per layer); CNC forum threads on parts not cut '
               'through because the cut depth was set to nominal on oversize sheet or typed short'),
]


def _f_block_inches(g, rng):
    """One part inserted as a block drawn in inches into the mm drawing, without unit scaling: that part (outline,
    openings, holes) is 25.4x too small, the rest of the file is right."""
    if len(g.parts) < 3: return None
    g = clone(g); k = 1 / 25.4
    cand = [p for p in g.parts if p.outer.area > 20000]
    if not cand: return None
    p = rng.choice(cand); c = p.outer.centroid
    p.outer = affinity.scale(p.outer, k, k, origin=c)
    p.inner = [affinity.scale(i, k, k, origin=c) for i in p.inner]
    for f in p.features:
        f.geom = affinity.scale(f.geom, k, k, origin=c); f.r = f.r * k if f.r else f.r
    return g


def _f_pocket_through(g, rng):
    """A pocket (housing, recess) drawn on the through-cut layer instead of its pocket layer: it is cut out as an
    opening through the part."""
    g = clone(g)
    cand = [(p, f) for p in g.parts for f in p.features
            if f.op == 'pocket' and f.geom.geom_type == 'Polygon' and f.geom.area > 100 and f.geom.within(p.outer)
            and p.outer.exterior.distance(f.geom) > 2 and not any(f.geom.intersects(i) for i in p.inner)]
    if not cand: return None
    p, f = rng.choice(cand)
    p.features.remove(f)
    p.inner.append(Polygon(f.geom.exterior.coords))
    return g


def _f_slot_short(g, rng):
    """One slot of a family of identical slots (same width and length) drawn 30 % shorter: the mating part's full
    width no longer passes through it."""
    if not g.thickness: return None
    g = clone(g); th = g.thickness
    sl = [(p, i, w, ang) for p in g.parts for i, w, ang in _slots(p, th)]
    def L(i):
        return _rect_axes(i)[2]
    cand = [(p, i, w, ang) for p, i, w, ang in sl
            if sum(1 for q, j, w2, a2 in sl if j is not i and abs(w2 - w) < 0.2 and abs(L(j) - L(i)) < 0.5) >= 1
            and L(i) >= 30]
    rng.shuffle(cand)
    for p, i, w, ang in cand:
        c = i.centroid
        m = affinity.rotate(i, -ang, origin=c)
        m = affinity.scale(m, 0.7, 1.0, origin=c)                 # long axis is x after aligning
        m = affinity.rotate(m, ang, origin=c)
        if not m.is_valid or m.is_empty or not m.within(p.outer): continue
        _replace_inner(p, i, m)
        return g
    return None


FAULTS += [
    Mut('gm46', 'One part is a block drawn in inches, inserted unscaled into the mm drawing (that part 25.4x too small)',
        'The block\'s own units were ignored on insert: one part of the kit comes out at 1/25 size - a 600 mm side '
        'becomes a 24 mm chip with slots and holes far below any bit size - and the furniture is a part short',
        _f_block_inches,
        source='AutoCAD INSERT / INSUNITS block scaling (blocks drawn in another unit are scaled only if both '
               'drawings declare units); Fusion 360 / SketchUp component import unit mismatches; CNC forum threads on '
               'one part of a DXF coming out tiny after combining files from different sources'),
    Mut('gm47', 'A pocket (housing / recess) drawn on the through-cut layer: cut out as an opening through the part',
        'The recess for a shelf, back panel or hardware was meant to stop part-way; on the profile layer it is cut '
        'through the sheet: the panel gets a hole where it should have a housing, a long housing nearly cuts the '
        'panel in two, and whatever sat in the recess has nothing to sit on',
        _f_pocket_through,
        source='Opendesk CAM layer convention (TOP-POCKET-INSIDE_<depth> vs TOP-CUT-INSIDE_<sheet>; depth from the '
               'layer); Vectric toolpath templates per layer; ShopBot / Vectric forum threads on pockets cut through '
               'because the vector sat on the profile layer'),
    Mut('gm48', 'One slot of a set of identical slots drawn 30 % shorter (the mating part does not pass through)',
        'Slots receive a mating part of a fixed width: a slot shortened by an edit (stretched / trimmed vector) '
        'stops the part - it cannot be assembled without recutting or chiselling the slot, which ruins a press fit',
        _f_slot_short,
        source='Opendesk / WikiHouse slot-joint guidance (slot length = mating part width + clearance); Fab Academy '
               'press-fit assignments (slots must match the mating part); CAD forum threads on stretch / trim edits '
               'that changed one copy of an arrayed feature'),
]


# ---- shard g, round 2 ----------------------------------------------------------------------------------------------

def _g_pocket_thin_floor(g, rng):
    """One pocket / rebate deepened to leave only 1 mm of sheet under it (depth = sheet thickness - 1 mm)."""
    if not g.thickness or g.thickness < 6: return None
    g = clone(g)
    cand = [f for p in g.parts for f in p.features if f.op == 'pocket' and f.depth and f.depth < g.thickness - 2.0
            and f.geom is not None and f.geom.area > 100]
    if not cand: return None
    f = rng.choice(cand)
    f.depth = round(g.thickness - 1.0, 3)
    return g


def _g_thin_finger(g, rng):
    """A 4 mm wide, 40 mm long finger / tab sticking out of a part edge (a tab drawn far narrower than the sheet)."""
    th = g.thickness or g.thickness_est
    if not th or th < 9: return None
    g = clone(g)
    cand = [p for p in sorted(g.parts, key=lambda q: -q.outer.area)[:10] if p.outer.area > 20000 and p.outer.is_valid]
    rng.shuffle(cand)
    w, L = 4.0, 40.0
    for p in cand:
        ext = p.outer.exterior
        coords = list(ext.coords)
        segs = [(coords[i], coords[i + 1]) for i in range(len(coords) - 1) if math.dist(coords[i], coords[i + 1]) > 60]
        rng.shuffle(segs)
        for (x0, y0), (x1, y1) in segs[:6]:
            d = math.dist((x0, y0), (x1, y1)); ux, uy = (x1 - x0) / d, (y1 - y0) / d
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            for nx, ny in ((-uy, ux), (uy, -ux)):
                if p.outer.contains(Point(mx + nx * 2, my + ny * 2)): continue     # (nx, ny) must point outward
                fin = Polygon([(mx - ux * w / 2 - nx * 0.5, my - uy * w / 2 - ny * 0.5),
                               (mx + ux * w / 2 - nx * 0.5, my + uy * w / 2 - ny * 0.5),
                               (mx + ux * w / 2 + nx * L, my + uy * w / 2 + ny * L),
                               (mx - ux * w / 2 + nx * L, my - uy * w / 2 + ny * L)])
                if any(fin.buffer(5).intersects(o.outer) for o in g.parts if o is not p): continue
                if g.sheet is not None and not fin.within(g.sheet): continue
                new = p.outer.union(fin)
                if new.geom_type != 'Polygon' or len(new.interiors): continue
                p.outer = Polygon(new.exterior.coords)
                return g
    return None


def _g_hole_into_opening(g, rng):
    """A drilled hole moved so it breaks into the edge of a slot / cut-out of the same part (centre in solid sheet,
    r/2 from the opening: the bore bites half a radius into the opening)."""
    g = clone(g)
    cand = []
    for p in g.parts:
        ops = [i for i in p.inner if i.area > 200 and not any(f.geom is i for f in p.features)]
        hs = [f for f in holes(p) if f.r >= 1.5]
        if ops and hs: cand.append((p, ops, hs))
    rng.shuffle(cand)
    for p, ops, hs in cand:
        f = rng.choice(hs)
        c = f.geom.centroid
        o = min(ops, key=lambda i: i.distance(c))
        a, b = nearest_points(o.exterior, c)
        d = a.distance(b)
        if d < 1e-6 or d > 150: continue
        k = (d - f.r / 2) / d                       # centre ends r/2 from the opening: the bore overlaps it
        dx, dy = (a.x - b.x) * k, (a.y - b.y) * k
        m = affinity.translate(f.geom, dx, dy)
        if not m.within(p.outer) or p.outer.exterior.distance(m) < 3: continue
        if any(m.intersects(h.geom) for h in p.features if h is not f and h.op == 'hole'): continue
        if m.intersection(o).area < 1.0: continue
        if f.geom in p.inner: p.inner[p.inner.index(f.geom)] = m
        f.geom = m
        return g
    return None


FAULTS += [
    Mut('gm50', 'Pocket / rebate drawn 1 mm short of the sheet thickness (1 mm floor left)',
        'Sheet goods are not as thick as their name: plywood is allowed several tenths of a mm either way and varies '
        'across one sheet, and the spoilboard is never perfectly flat. A pocket that leaves 1 mm of floor either breaks '
        'through where the sheet is thin (a hole in a visible face) or leaves a floor so weak it cracks as soon as a '
        'fitting or shelf loads it',
        _g_pocket_thin_floor,
        source='EN 315 plywood dimensional tolerances (thickness tolerance grows with nominal thickness, about ±0.7 mm '
               'for 18 mm); ShopBot "Holding Down Material for Cutting" (onion skin 0.25-0.76 mm is the deliberate '
               'cut-through margin, so a 1 mm floor is within the machine\'s own Z error); Vectric / Fusion pocketing '
               'guides (leave a minimum floor, zero Z to the spoilboard for through cuts)'),
    Mut('gm51', 'A 4 mm wide finger / tab sticking 40 mm out of a part edge',
        'A strip of ply or MDF much narrower than the sheet is thick has almost no cross-grain strength: it breaks '
        'off while the part is cut (the cutter deflects it, the vacuum cannot hold it) or the first time the part is '
        'handled or assembled, so the tab or locating finger it was meant to be is missing',
        _g_thin_finger,
        source='Opendesk design guidelines (minimum feature / tab width about the sheet thickness); Fab Academy CNC '
               'week notes (thin features snap off during milling, keep features wider than the bit and the sheet); '
               'ShopBot hold-down guide (small, narrow pieces are thrown or break when not held)'),
    Mut('gm52', 'A drilled hole breaking into the edge of a slot / cut-out in the same part',
        'A bore that overlaps an opening has no full wall: the drill wanders into the gap and tears out the slot edge, '
        'and the screw, dowel or cam it was drilled for has nothing to grip on one side, so the fitting pulls out and '
        'the slot loses its clean edge for the mating part',
        _g_hole_into_opening,
        source='Häfele / Hettich fitting instructions (bores in solid material, minimum distance to panel edges and '
               'other machining); Opendesk making guide (check hole positions against slots and cut-outs); woodworking '
               'forum reports of dowel / cam bores breaking into adjacent cut-outs'),
]


def _g_pocket_too_narrow(g, rng):
    """A pocket / groove redrawn 2 mm wide (narrower than any bit that cuts furniture sheet), same length and place."""
    g = clone(g)
    cand = [(p, f) for p in g.parts for f in p.features if f.op == 'pocket' and f.geom is not None
            and f.geom.geom_type == 'Polygon' and f.geom.area > 150 and f.geom.within(p.outer)]
    rng.shuffle(cand)
    for p, f in cand:
        r, w, L, ang = _rect_axes(f.geom)
        if L < 20 or w < 6: continue
        c = f.geom.centroid
        a = math.radians(ang); ux, uy = math.cos(a), math.sin(a); nx, ny = -uy, ux
        hw, hl = 1.0, L / 2
        m = Polygon([(c.x - ux * hl - nx * hw, c.y - uy * hl - ny * hw), (c.x + ux * hl - nx * hw, c.y + uy * hl - ny * hw),
                     (c.x + ux * hl + nx * hw, c.y + uy * hl + ny * hw), (c.x - ux * hl + nx * hw, c.y - uy * hl + ny * hw)])
        if not m.within(p.outer): continue
        f.geom = m
        return g
    return None


def _g_mortise_short(g, rng):
    """One through slot (mortise for a mating sheet's tab) drawn 30 % shorter along its length."""
    if not g.thickness: return None
    g = clone(g)
    cand = [(p, i, ang) for p in g.parts for i, w, ang in _slots(p, g.thickness)]
    rng.shuffle(cand)
    for p, i, ang in cand:
        c = i.centroid
        m = affinity.rotate(i, -ang, origin=c)
        m = affinity.scale(m, 0.7, 1.0, origin=c)
        m = affinity.rotate(m, ang, origin=c)
        if m.is_empty or not m.is_valid or m.area < 30: continue
        _replace_inner(p, i, m)
        return g
    return None


def _g_pocket_thin_wall(g, rng):
    """A pocket / housing moved toward the nearest part edge so only a 1 mm wall of sheet is left beside it."""
    g = clone(g)
    cand = [(p, f) for p in g.parts for f in p.features if f.op == 'pocket' and f.geom is not None
            and f.geom.geom_type == 'Polygon' and f.geom.area > 150 and f.geom.within(p.outer)
            and p.outer.exterior.distance(f.geom) > 6]
    rng.shuffle(cand)
    for p, f in cand:
        a, b = nearest_points(f.geom.boundary, p.outer.exterior)
        d = a.distance(b)
        if d < 1e-6: continue
        k = (d - 1.0) / d
        m = affinity.translate(f.geom, (b.x - a.x) * k, (b.y - a.y) * k)
        if not m.within(p.outer) or p.outer.exterior.distance(m) < 0.8: continue
        if any(m.intersects(i) for i in p.inner): continue
        if any(m.intersects(h.geom) for h in p.features if h is not f and h.op == 'pocket'): continue
        f.geom = m
        return g
    return None


FAULTS += [
    Mut('gm53', 'A pocket / groove drawn 2 mm wide (narrower than any bit that cuts furniture sheet)',
        'A pocket is cleared with a round bit, so it can be no narrower than the bit: 2 mm is under the 1/8" '
        '(3.175 mm) bit that is the smallest used on furniture sheet, and far under the 6 mm bits pockets are '
        'normally cleared with. CAM leaves the groove out (VCarve: tool too large for the vector) or cuts it with a '
        'bigger bit, so the panel, back or hardware that should sit in it does not fit',
        _g_pocket_too_narrow,
        source='Vectric VCarve/Aspire pocket toolpath ("tool too large": no toolpath for vectors narrower than the '
               'tool); Amana compression bit range (smallest through-cutting bit 1/8"); Opendesk design guidelines '
               '(design every feature for the 6 mm tool); Fab Academy CNC week (no feature narrower than the bit)'),
    Mut('gm54', 'A mortise (through slot for a tab) drawn 30 % shorter than the tab it takes',
        'Slot-and-tab furniture locates parts by tabs that pass through matching mortises: a mortise drawn short '
        '(an edit applied to one copy, or scaled with the part) stops the tab, the parts cannot be assembled without '
        'recutting or chiselling, and forcing it splits the ply',
        _g_mortise_short,
        source='Opendesk / AtFAB slot-and-tab joint libraries (mortise length = tab width + clearance); Digital Wood '
               'Joints library (tab and slot drawn as a pair); Fab Academy press-fit assignments (mismatched tab and '
               'slot sizes keep kits from assembling); CNC forum reports of a single slot left at an old size'),
    Mut('gm55', 'A pocket / housing placed 1 mm from the part edge (1 mm wall of sheet left beside it)',
        'The wall between a housing and the panel edge carries the shelf / back / hardware in the pocket: 1 mm of ply '
        'or MDF beside a pocket is torn off by the cutter or splits as soon as the part in the housing is loaded, '
        'leaving the housing open on the edge and the joint loose',
        _g_pocket_thin_wall,
        source='Opendesk design guidelines (minimum material around pockets and housings); Hettich / Häfele fitting '
               'instructions (minimum edge distance for housings and bores in panel material); ShopBot / Vectric '
               'forum reports of thin pocket walls breaking out during cutting'),
]


def _g_twins(g, pred):
    """Parts (area > 5000) that have an identical twin in the file (_congruent) and satisfy pred(part)."""
    big = [p for p in g.parts if p.outer.area > 5000 and pred(p)]
    return [a for a in big if any(a is not b and _congruent(a, b) for b in big)]


def _g_pocket_into_opening(g, rng):
    """A pocket / housing moved so it overlaps a through slot / cut-out of the same part by half its width."""
    g = clone(g)
    cand = [(p, f) for p in g.parts for f in p.features if f.op == 'pocket' and f.geom is not None
            and f.geom.geom_type == 'Polygon' and f.geom.area > 150 and f.geom.within(p.outer)
            and not any(f.geom.intersects(i) for i in p.inner)]
    rng.shuffle(cand)
    for p, f in cand:
        ops = [i for i in p.inner if i.area > 200 and not any(h.geom is i for h in p.features)]
        if not ops: continue
        o = min(ops, key=lambda i: i.distance(f.geom))
        a, b = nearest_points(f.geom, o)
        d = a.distance(b)
        if d < 1e-6 or d > 200: continue
        r, w, L, ang = _rect_axes(f.geom)
        k = (d + w / 2) / d
        m = affinity.translate(f.geom, (b.x - a.x) * k, (b.y - a.y) * k)
        if not m.within(p.outer) or p.outer.exterior.distance(m) < 2: continue
        ov = m.intersection(o).area
        if ov < 0.15 * m.area or ov > 0.85 * m.area or o.within(m): continue
        f.geom = m
        return g
    return None


def _g_pocket_dropped(g, rng):
    """One pocket / housing missing on one of two (or more) identical parts (its twin still has it)."""
    g = clone(g)
    pk = lambda p: [f for f in p.features if f.op == 'pocket' and f.geom is not None and f.geom.area > 100]
    cand = _g_twins(g, lambda p: len(pk(p)) >= 1)
    rng.shuffle(cand)
    for p in cand:
        p.features.remove(rng.choice(pk(p)))
        return g
    return None


def _g_slot_dropped(g, rng):
    """One through slot (for a mating sheet) missing on one of two (or more) identical parts."""
    if not g.thickness: return None
    g = clone(g)
    cand = _g_twins(g, lambda p: len(_slots(p, g.thickness)) >= 1)
    rng.shuffle(cand)
    for p in cand:
        i, w, ang = rng.choice(_slots(p, g.thickness))
        p.inner.remove(i)
        for f in list(p.features):
            if f.geom is i: p.features.remove(f)
        return g
    return None


FAULTS += [
    Mut('gm56', 'A pocket / housing overlapping a through slot or cut-out by half its width',
        'Where a housing runs into a through opening it has no floor and no side wall: the shelf / back / fitting that '
        'should sit in the housing falls into the opening, the thin sheet left between the two cuts breaks out, and '
        'the slot loses the edge its mating part bears on',
        _g_pocket_into_opening,
        source='Opendesk design guidelines (keep material between pockets and through cuts); Vectric / Fusion CAM '
               'notes (check pocket and profile toolpaths do not overlap unintentionally); cabinet-making practice '
               '(housings and through mortises laid out from the same datum, never crossing)'),
    Mut('gm57', 'One pocket / housing missing on one of two identical parts (its twin still has it)',
        'Copies of a part carry the same housings and rebates; when one pocket is lost on export (hidden layer, '
        'deleted with a duplicate) that copy has no housing for its shelf / back / fitting, and the piece cannot be '
        'assembled square without recutting',
        _g_pocket_dropped,
        source='Opendesk making guide (check every part against the assembly drawing before cutting); Vectric "find '
               'duplicate vectors" clean-up deleting needed geometry; CNC forum stories of pockets missing on one '
               'copy after a layer was turned off for export'),
    Mut('gm58', 'One through slot missing on one of two identical parts (its twin still has it)',
        'In slot-together furniture every slot receives a part: a copy without one of its slots has nowhere for the '
        'mating sheet or tab to go, so the kit does not assemble and the part is recut',
        _g_slot_dropped,
        source='Opendesk / AtFAB slot-together assembly guides (each slot takes a named part); WikiHouse design guide; '
               'CNC forum stories of geometry lost on export (frozen layers, deleted duplicates)'),
]


def _h_notch_no_dogbones(g, rng):
    """Every dog-boned slot-together edge notch of one part exported with sharp 90-degree inner corners."""
    if not g.thickness: return None
    g = clone(g)
    cand = [p for p in g.parts if any(_core_rect(n) is not None for n, w, L, ang in _edge_slots(p, g.thickness))]
    rng.shuffle(cand)
    for p in cand:
        o = Polygon(p.outer.exterior.coords); n_done = 0
        for n, w, L, ang in _edge_slots(p, g.thickness):
            core = _core_rect(n)
            if core is None: continue
            lobes = n.difference(core.buffer(0.01, join_style=2))
            if lobes.is_empty: continue
            new = o.union(lobes.buffer(0.01, join_style=2))
            if new.geom_type != 'Polygon' or len(new.interiors): continue
            o = Polygon(new.exterior.coords); n_done += 1
        if not n_done: continue
        p.outer = o
        return g
    return None


def _h_outline_inside_layer(g, rng):
    """One big part's outline put on the cut-INSIDE layer (tool offset to the inside of the line) in a file that
    uses the Opendesk-style INSIDE / OUTSIDE layer convention."""
    outs = [p for p in g.parts if 'OUTSIDE' in p.layer.upper()]
    if len(outs) < 2: return None
    g = clone(g)
    cand = [p for p in g.parts if 'OUTSIDE' in p.layer.upper() and p.outer.area > 20000
            and not any(q is not p and p.outer.within(q.outer) for q in g.parts)]
    if not cand: return None
    p = rng.choice(cand)
    import re
    p.layer = re.sub('(?i)OUTSIDE', lambda m: 'INSIDE' if m.group(0).isupper() else 'inside', p.layer)
    return g


def _h_pocket_thin_floor(g, rng):
    """One blind pocket / bore drawn so deep that only 0.5 mm of sheet is left under it."""
    if not g.thickness: return None
    g = clone(g)
    cand = [f for p in g.parts for f in p.features
            if f.op in ('pocket', 'hole') and f.depth and 1.5 <= g.thickness - f.depth and f.geom.within(p.outer)]
    if not cand: return None
    f = rng.choice(cand)
    f.depth = round(g.thickness - 0.5, 3)
    import re
    if re.search(r'_\d+(?:\.\d+)?\s*MM\s*$', f.layer.upper()):
        f.layer = re.sub(r'(?i)_\d+(?:\.\d+)?(\s*MM\s*)$', lambda m: '_%.3f%s' % (f.depth, m.group(1)), f.layer)
    return g


FAULTS += [
    Mut('gm60', 'Slot-together edge notches exported with sharp inner corners (dog-bones / T-bones missing)',
        'A router bit cannot cut a sharp inside corner: it leaves a radius of half the bit (3 mm for a 6 mm bit) in '
        'both bottom corners of the notch. The mating part, which has square corners, sits on those radii and stops '
        '3+ mm short, so the slot-together joint never seats and the furniture racks; filing out every corner by hand '
        'is the usual fix',
        _h_notch_no_dogbones,
        source='Opendesk design guidelines (dog-bone or T-bone every internal corner of a joint); Fab Academy '
               'computer-controlled machining week (press-fit joints need dog-bone fillets); Fusion 360 "Dogbone" '
               'add-in documentation; ShopBot / Vectric forum threads on slot joints that will not close because of '
               'corner radii left by the bit'),
    Mut('gm61', 'Part outline drawn on the cut-INSIDE layer (tool offset to the wrong side of the line)',
        'Layer-driven CAM (Opendesk convention: CUT-OUTSIDE for part outlines, CUT-INSIDE for openings) offsets the '
        'tool by its radius to the named side: an outline on the INSIDE layer is cut with the bit inside the line, so '
        'the part comes out one bit diameter (6-9 mm) too small in each direction - every tab is too short and every '
        'slot-together edge misses its mate',
        _h_outline_inside_layer,
        source='Opendesk CAM layer conventions (TOP-CUT-OUTSIDE / TOP-CUT-INSIDE with depth suffix); Vectric VCarve '
               'profile toolpath "Machine vectors: Outside / Inside / On"; ShopBot and Fusion 360 forum threads on parts '
               'cut undersize by the bit diameter because the wrong offset side was chosen'),
    Mut('gm62', 'Blind pocket / bore drawn so deep that only 0.5 mm of sheet is left under it',
        'Plywood and MDF sheets vary by +/- 0.5-0.8 mm in thickness and the spoilboard is never perfectly flat: a '
        'pocket leaving 0.5 mm breaks through on part of the sheet, and the paper-thin floor tears out under a hinge '
        'cup or Minifix housing - the fitting has nothing to hold on and the show face is holed',
        _h_pocket_thin_floor,
        source='APA / EN 315 plywood thickness tolerances (+/-0.5 mm and more on 18 mm); Blum and Hettich hinge-cup '
               'drilling depths (13 mm in 16-19 mm boards, never through-thin); Häfele Minifix housing depth per board '
               'thickness (14.0 in 19 mm, 13.5 in 18 mm); ShopBot / Vectric forum threads on pockets breaking through '
               'because of sheet thickness variation'),
]


def _h_bore_into_opening(g, rng):
    """One drilled hole moved so it breaks 1 mm into the wall of a neighbouring through opening (slot / cut-out)."""
    g = clone(g)
    cand = []
    for p in g.parts:
        ops = [i for i in p.inner if i.area > 100]
        if not ops: continue
        for f in holes(p):
            others = [i for i in ops if i is not f.geom]
            if not others: continue
            j = min(others, key=lambda i: i.distance(f.geom))
            if f.geom.distance(j) > 3: cand.append((p, f, j))
    rng.shuffle(cand)
    for p, f, j in cand:
        a, b = nearest_points(f.geom, j)
        d = a.distance(b)
        if d < 1e-6: continue
        k = (d + 1.0) / d                                      # past the wall by 1 mm: the bore cuts into the opening
        m = affinity.translate(f.geom, (b.x - a.x) * k, (b.y - a.y) * k)
        if not m.within(p.outer) or p.outer.exterior.distance(m) < 3: continue
        if m.within(j) or m.intersection(j).area < 1: continue
        if any(m.intersects(o) for o in p.inner if o is not f.geom and o is not j): continue
        if any(m.intersects(o.geom) for o in p.features if o is not f and o.geom is not j and o.geom is not f.geom): continue
        if f.geom in p.inner: p.inner[p.inner.index(f.geom)] = m
        f.geom = m
        return g
    return None


def _h_rows(p, rmax=12.0):
    """Regular rows in p: lists of >= 4 same-size drilled holes on one line at one pitch (sorted along the line)."""
    hs = [f for f in p.features if f.op == 'hole' and f.r and f.r <= rmax and f.geom is not None]
    byr = {}
    for f in hs: byr.setdefault(round(f.r, 1), []).append(f)
    rows = []
    for r, fs in byr.items():
        if len(fs) < 4 or len(fs) > 200: continue
        cs = [(f, f.geom.centroid) for f in fs]
        for f0, c0 in cs:
            for f1, c1 in cs:
                if f1 is f0: continue
                d = c0.distance(c1)
                if d < 8: continue
                ux, uy = (c1.x - c0.x) / d, (c1.y - c0.y) / d
                on = [(((c.x - c0.x) * ux + (c.y - c0.y) * uy), f) for f, c in cs
                      if abs((c.x - c0.x) * -uy + (c.y - c0.y) * ux) < 0.3]
                on.sort(key=lambda t: t[0])
                ts = [t for t, _ in on]
                if len(on) >= 4 and all(abs((ts[i + 1] - ts[i]) - d) < 0.5 for i in range(len(ts) - 1)) and ts[0] == 0:
                    rows.append([f for _, f in on])
    return rows


def _h_row_wrong_size(g, rng):
    """One hole of a regular drilled row (shelf pins / System 32 / fitting screws) drawn 3 mm larger in diameter."""
    g = clone(g)
    cand = [(p, row) for p in g.parts for row in _h_rows(p)]
    if not cand: return None
    p, row = rng.choice(cand)
    f = row[rng.randrange(1, len(row) - 1)]
    c = f.geom.centroid; nr = f.r + 1.5
    m = Point(c.x, c.y).buffer(nr, 32)
    if not m.within(p.outer) or p.outer.exterior.distance(m) < 1: return None
    if any(m.intersects(o) for o in p.inner if o is not f.geom): return None
    if any(m.intersects(o.geom) for o in p.features if o is not f and o.geom is not f.geom): return None
    if f.geom in p.inner: p.inner[p.inner.index(f.geom)] = m
    f.geom = m; f.r = nr
    return g


def _h_counterbore_offset(g, rng):
    """A counterbore (larger concentric bore / pocket round a through hole) drawn 2 mm off its hole's centre."""
    g = clone(g)
    cand = []
    for p in g.parts:
        cs = [f for f in p.features if f.r and f.op in ('hole', 'pocket') and f.geom is not None]
        for a in cs:
            for b in cs:
                if b is a or b.r < a.r + 2.5: continue
                if a.geom.centroid.distance(b.geom.centroid) < 0.2 and b.geom not in p.inner:
                    cand.append((p, a, b))
    rng.shuffle(cand)
    for p, a, b in cand:
        ang = rng.uniform(0, 2 * math.pi)
        dx, dy = 2.0 * math.cos(ang), 2.0 * math.sin(ang)
        m = affinity.translate(b.geom, dx, dy)
        if not m.within(p.outer): continue
        if any(m.intersects(o.geom) for o in p.features if o is not a and o is not b and o.geom is not a.geom): continue
        b.geom = m
        return g
    return None


FAULTS += [
    Mut('gm63', 'Drilled hole breaks 1 mm into the wall of a neighbouring slot / cut-out',
        'A bore that cuts into an opening\'s wall leaves a half-moon bite in the slot: the screw or dowel has no '
        'wall to bite on that side, the drill wanders into the void and tears the edge, and the mating sheet in the '
        'slot now has a gap at that point - the fixing pulls out and the joint goes loose',
        _h_bore_into_opening,
        source='Häfele / Hettich drilling guides (screw and dowel bores need full material round them; '
               'Minifix bolt hole fully in solid board); Opendesk design guidelines (keep fixings clear of slots by '
               'at least the sheet thickness); woodworking forum threads on pilot holes breaking into mortises'),
    Mut('gm64', 'One hole of a regular drilled row drawn 3 mm larger in diameter than the others',
        'The holes of a shelf-pin / System 32 / fitting row take identical pins or screws: one hole 3 mm oversize '
        '(a block swapped or a circle resized by mistake) leaves its pin or screw loose, so that shelf rocks or that '
        'hinge / runner screw spins out',
        _h_row_wrong_size,
        source='Hettich "Ratgeber Möbeltechnik" (System 32: Ø5 holes at 32 mm pitch, one drill for the whole row); '
               'Häfele shelf support catalogue (Ø5 pins in Ø5 holes); CNC forum threads on one wrong hole in a row '
               'after a block was replaced'),
    Mut('gm65', 'Counterbore drawn 2 mm off the centre of its through hole',
        'A counterbore must be concentric with its bolt hole: offset by 2 mm, the bolt or barrel-nut head no longer '
        'sits flat in it - it is pushed to one side, binds on the wall and stands proud, and the through hole is '
        'half blocked so the bolt will not line up with its nut',
        _h_counterbore_offset,
        source='Opendesk / AtFAB bolt counterbore details (counterbore and clearance hole on one centre); '
               'Häfele connector fittings (head bore concentric with the shank bore); machinists\' drawing standards '
               '(counterbore called out on the hole axis)'),
]


def _h_housings(p, th):
    """Blind housing pockets (dados / trenches a mating sheet sits in): rectangle-like, ~ sheet thickness wide,
    >= 2x as long, inside the part."""
    out = []
    for f in p.features:
        if f.op != 'pocket' or f.r or f.geom is None or f.geom.geom_type != 'Polygon': continue
        r, w, L, ang = _rect_axes(f.geom)
        if 0.95 * th <= w <= 1.3 * th and L >= 2 * w and f.geom.area > 0.8 * r.area:
            out.append((f, w, ang))
    return out


def _h_housing_no_dogbones(g, rng):
    """The dog-boned housing pockets of one part exported with sharp 90-degree corners."""
    if not g.thickness: return None
    g = clone(g)
    cand = [p for p in g.parts if any(_core_rect(f.geom) is not None for f, w, ang in _h_housings(p, g.thickness))]
    if not cand: return None
    p = rng.choice(cand); n = 0
    for f, w, ang in _h_housings(p, g.thickness):
        core = _core_rect(f.geom)
        if core is None: continue
        f.geom = Polygon(core.exterior.coords); n += 1
    return g if n else None


def _h_housing_narrow(g, rng):
    """The housing pockets of one part drawn 1.5 mm narrower than the sheet that has to sit in them."""
    if not g.thickness: return None
    g = clone(g); th = g.thickness
    cand = [p for p in g.parts if _h_housings(p, th)]
    if not cand: return None
    p = rng.choice(cand); n = 0
    for f, w, ang in _h_housings(p, th):
        c = f.geom.centroid
        k = (th - 1.5) / w
        m = affinity.rotate(f.geom, -ang, origin=c)
        m = affinity.scale(m, 1.0, k, origin=c)
        m = affinity.rotate(m, ang, origin=c)
        if not m.is_valid or m.is_empty: continue
        f.geom = m; n += 1
    return g if n else None


def _h_hole_on_edge(g, rng):
    """One drilled hole moved so its centre sits 40 % of its radius inside the part outline: the bore straddles the
    edge (hole snapped to the edge line, or the outline trimmed after the holes were placed)."""
    g = clone(g)
    cand = [(p, f) for p in g.parts for f in holes(p) if f.geom is not None and p.outer.exterior.distance(f.geom) > 2]
    rng.shuffle(cand)
    for p, f in cand:
        c = f.geom.centroid
        q = p.outer.exterior.interpolate(p.outer.exterior.project(c))          # nearest point on the outline
        d = c.distance(q)
        if d < 1e-6: continue
        k = (d - 0.4 * f.r) / d
        m = affinity.translate(f.geom, (q.x - c.x) * k, (q.y - c.y) * k)
        mc = m.centroid
        if not p.outer.contains(mc) or not m.intersects(p.outer.exterior): continue
        if any(m.intersects(o) for o in p.inner if o is not f.geom): continue
        if any(m.intersects(o.geom) for o in p.features if o is not f and o.geom is not f.geom): continue
        if any(m.intersects(o.outer) for o in g.parts if o is not p): continue
        if f.geom in p.inner: p.inner[p.inner.index(f.geom)] = m
        f.geom = m
        return g
    return None


FAULTS += [
    Mut('gm66', 'Housing (dado) pockets exported with sharp corners where the file dog-bones its other housings',
        'A pocketing bit leaves its radius in every corner of a housing: the square end and edges of the shelf or '
        'divider that sits in it bottom on those fillets, so the part stands proud of the housing by up to the bit '
        'radius, the joint does not close and the glue line starves',
        _h_housing_no_dogbones,
        source='Opendesk design guidelines (dog-bone every internal corner a part sits in, pockets included); Fusion 360 '
               'Dogbone add-in (applies to pockets and slots); ShopBot / Vectric forum threads on dados that shelves '
               'will not drop into because of corner radii'),
    Mut('gm67', 'Housing (dado) pockets drawn 1.5 mm narrower than the sheet that sits in them',
        'A shelf or divider sheet does not go into a housing narrower than itself: 1.5 mm too tight cannot be forced '
        'or sanded in on site, so every housing on that part has to be re-cut or chiselled out',
        _h_housing_narrow,
        source='Opendesk / WikiHouse making notes (housings drawn at measured sheet thickness + clearance); '
               'plywood thickness tolerance (EN 315: sheets vary by about +/-0.5 mm, metric "18 mm" ply often measures 17.2-17.5 mm); '
               'woodworking guides on dado width vs undersized plywood'),
    Mut('gm68', 'Drilled hole straddles the part edge (centre just inside the outline, bore breaks out of the edge)',
        'A bore that crosses the outline is cut open along the edge: the screw or dowel has an open groove instead of '
        'a hole and nothing to grip, the drill catches the edge and splinters the face veneer, and the part edge gets '
        'a bite where the mating part should sit flush',
        _h_hole_on_edge,
        source='Häfele / Hettich drilling guides (minimum edge distance for every bore; System 32 line 37 mm from the '
               'edge); CAD snap errors (circle centre snapped to the edge line / outline offset after the holes were '
               'placed) reported in Fusion 360 and Vectric forum threads; Opendesk design guidelines (hardware holes '
               'fully within the part with a sheet thickness of material round them)'),
]


def _h_row_hole_shallow(g, rng):
    """One hole of a regular drilled row put on a drill layer with half the depth of its row-mates (wrong layer /
    depth picked for that circle)."""
    import re
    g = clone(g)
    cand = [(p, row) for p in g.parts for row in _h_rows(p) if all(f.depth for f in row)
            and len({round(f.depth, 1) for f in row}) == 1]
    if not cand: return None
    p, row = rng.choice(cand)
    f = row[rng.randrange(1, len(row) - 1)]
    f.depth = round(f.depth / 2, 3)
    if re.search(r'_\d+(?:\.\d+)?\s*MM\s*$', f.layer.upper()):
        f.layer = re.sub(r'(?i)_\d+(?:\.\d+)?(\s*MM\s*)$', lambda m: '_%.3f%s' % (f.depth, m.group(1)), f.layer)
    return g


FAULTS += [
    Mut('gm69', 'One hole of a regular drilled row on a drill layer half as deep as the rest of the row',
        'Layer-driven CAM drills every circle to the depth its layer names: one hole of a bolt / dowel / shelf-pin '
        'row put on a shallower layer stops half-way, so its bolt will not pass, its dowel stands proud and keeps '
        'the joint open, or its shelf pin falls out - found only at assembly',
        _h_row_hole_shallow,
        source='Opendesk CAM layer conventions (drill depth in the layer name, e.g. TOP-HOLE-8.000MM-DIAM_12.000MM); '
               'Vectric / Fusion 360 layer-based drilling (depth set per layer or per operation); Hettich System 32 '
               '(all holes of a line drilled to one depth for the pins); forum threads on single holes left short '
               'after a circle landed on the wrong layer'),
]


# ---- shard k, round 3 ----------------------------------------------------------------------------------------------

def _k_feats_ok(p, outer, gap=2.0):
    """Every opening and feature of p still inside `outer` with >= gap mm of material to its edge."""
    for i in p.inner:
        if not i.within(outer) or outer.exterior.distance(i) < gap: return False
    for f in p.features:
        if f.geom is None or f.geom in p.inner: continue
        if f.op == 'pocket' and f.geom.intersects(p.outer.exterior): continue      # edge rebates stay edge rebates
        if not f.geom.within(outer) or outer.exterior.distance(f.geom) < gap: return False
    return True


def _k_twin_short(g, rng):
    """One of two identical parts drawn 3 mm shorter at one end (the copy was edited / trimmed, its twin was not)."""
    g = clone(g)
    cand = _g_twins(g, lambda p: True)
    rng.shuffle(cand)
    for p in cand:
        r, w, L, ang = _rect_axes(p.outer)
        if L < 150: continue
        c = p.outer.centroid
        o = affinity.rotate(p.outer, -ang, origin=c)
        minx, miny, maxx, maxy = o.bounds
        ends = [(minx + 3.0, maxx), (minx, maxx - 3.0)]
        rng.shuffle(ends)
        for x0, x1 in ends:
            box = Polygon([(x0, miny - 1), (x1, miny - 1), (x1, maxy + 1), (x0, maxy + 1)])
            m = o.intersection(box)
            if m.is_empty or m.geom_type != 'Polygon' or not m.is_valid: continue
            m = affinity.rotate(m, ang, origin=c)
            if not _k_feats_ok(p, m): continue
            p.outer = Polygon(m.exterior.coords)
            return g
    return None


def _k_row_pitch(g, rng):
    """One hole of a regular drilled row (shelf pins / System 32 / fitting screws) moved 3 mm ALONG the row: the
    32 mm pitch is broken, so it no longer lines up with its neighbours or the mating part."""
    g = clone(g)
    cand = [(p, row) for p in g.parts for row in _h_rows(p)]
    rng.shuffle(cand)
    for p, row in cand:
        f = row[rng.randrange(1, len(row) - 1)]
        a, b = row[0].geom.centroid, row[-1].geom.centroid
        d = a.distance(b)
        if d < 1e-6: continue
        ux, uy = (b.x - a.x) / d, (b.y - a.y) / d
        s = rng.choice((3.0, -3.0))
        m = affinity.translate(f.geom, ux * s, uy * s)
        if not m.within(p.outer) or p.outer.exterior.distance(m) < 2: continue
        if any(m.intersects(o) for o in p.inner if o is not f.geom): continue
        if any(m.distance(o.geom) < 1 for o in p.features if o is not f and o.geom is not None and o.geom is not f.geom): continue
        if f.geom in p.inner: p.inner[p.inner.index(f.geom)] = m
        f.geom = m
        return g
    return None


def _k_twin_hole_shift(g, rng):
    """One drilled hole (not part of a regular row) on one of two identical parts drawn 5 mm away from where its
    twin has it: the hole no longer lines up with the fitting / mating part."""
    g = clone(g)
    cand = _g_twins(g, lambda p: len(holes(p)) >= 1)
    rng.shuffle(cand)
    for p in cand:
        inrow = {id(f) for row, u, d in _hole_rows(p) for f in row}
        hs = [f for f in holes(p) if id(f) not in inrow and f.geom is not None]
        rng.shuffle(hs)
        for f in hs:
            for k in range(6):
                a = rng.uniform(0, 2 * math.pi)
                m = affinity.translate(f.geom, 5 * math.cos(a), 5 * math.sin(a))
                if not m.within(p.outer) or p.outer.exterior.distance(m) < 3: continue
                if any(m.distance(o) < 2 for o in p.inner if o is not f.geom): continue
                if any(m.distance(o.geom) < 2 for o in p.features if o is not f and o.geom is not None and o.geom is not f.geom): continue
                if f.geom in p.inner: p.inner[p.inner.index(f.geom)] = m
                f.geom = m
                return g
    return None


FAULTS += [
    Mut('gm90', 'One of two identical parts drawn 3 mm shorter at one end (copy trimmed / edited, its twin not)',
        'Paired parts (left and right sides, front and back rails, legs) carry the same load and must match: a side 3 mm '
        'short makes a cabinet or table rock on three feet, its shelves and top slope, slot-together joints and dowel '
        'holes on the mating parts stop lining up, and the error is found only at assembly when both copies are cut',
        _k_twin_short,
        source='Opendesk making guide (check that mirrored / paired parts are identical before cutting); Fusion 360 / '
               'SketchUp forum threads on one copy of a component edited after it was made unique; cabinet-making '
               'practice (pairs of sides cut together or to one stop so they match)'),
    Mut('gm91', 'One hole of a regular drilled row moved 3 mm along the row (32 mm pitch broken)',
        'System 32 lines, shelf-pin rows and runner / hinge-plate screw rows are drilled on one pitch so pins, cams and '
        'runners from the hardware maker fit them: one hole 3 mm off the pitch puts a shelf pin out of level (the shelf '
        'rocks), or leaves a runner / hinge screw with no hole where the fitting has one',
        _k_row_pitch,
        source='Hettich Ratgeber Möbeltechnik (System 32: Ø5 holes at 32 mm pitch, first and last hole equidistant from '
               'the edges); Häfele System 32 drilling jig (Unitool, fixed 32 mm pitch); Blum / Hettich runner mounting '
               'instructions (screw holes at fixed 32 mm multiples)'),
    Mut('gm92', 'One drilled hole on one of two identical parts drawn 5 mm away from where its twin has it',
        'Paired parts are drilled for the same fitting or mating part: when one copy\'s hole is snapped or nudged off '
        'position, its dowel, bolt or cam no longer meets the hole in the mating part, so the joint cannot be closed and '
        'the hole has to be plugged and re-drilled by hand',
        _k_twin_hole_shift,
        source='Häfele Minifix / dowel mounting instructions (bores on both parts must align; Minifix absorbs only +1 / '
               '-0.5 mm drilling error); Opendesk making guide (check paired parts match); CAD forum threads on objects '
               'nudged by arrow keys / snap after copying'),
]


def _k_twin_fat(g, rng):
    """One of two identical parts drawn 0.75 mm fat all round (tool compensation baked into that copy's geometry,
    then applied again by CAM): its outline grows, its openings shrink, its twin is right."""
    g = clone(g)
    cand = _g_twins(g, lambda p: True)
    rng.shuffle(cand)
    for p in cand:
        o = p.outer.buffer(0.75, join_style=2)
        if o.geom_type != 'Polygon': continue
        inner = [i.buffer(-0.75, join_style=2) for i in p.inner]
        if any(i.is_empty or i.geom_type != 'Polygon' for i in inner): continue
        for old, new in zip(list(p.inner), inner):
            for f in p.features:
                if f.geom is old:
                    f.geom = new
                    if f.r: f.r = max(0.1, f.r - 0.75)
        p.outer = Polygon(o.exterior.coords); p.inner = inner
        return g
    return None


def _k_twin_slot_shift(g, rng):
    """One through slot / cut-out (not a drilled hole) on one of two identical parts drawn 5 mm to one side of where
    its twin has it: the tab or mating sheet that goes through it no longer lines up."""
    g = clone(g)
    isopen = lambda p, i: i.area > 150 and not any(f.geom is i and f.op == 'hole' and f.r and f.r <= 12 for f in p.features)
    cand = _g_twins(g, lambda p: any(isopen(p, i) for i in p.inner))
    rng.shuffle(cand)
    for p in cand:
        ins = [i for i in p.inner if isopen(p, i)]
        rng.shuffle(ins)
        for i in ins:
            r, w, L, ang = _rect_axes(i)
            for a in (ang, ang + 90, ang + 180, ang + 270):
                t = math.radians(a)
                m = affinity.translate(i, 5 * math.cos(t), 5 * math.sin(t))
                if not m.within(p.outer) or p.outer.exterior.distance(m) < 3: continue
                if any(m.distance(o) < 3 for o in p.inner if o is not i): continue
                if any(m.distance(o.geom) < 2 for o in p.features if o.geom is not None and o.geom is not i): continue
                _replace_inner(p, i, m)
                return g
    return None


def _k_part_in_hole_tight(g, rng):
    """A small part nested inside another part's big cut-out, 1.5 mm from the cut-out's edge (part-in-part nesting
    with less clearance than the cutter: the two cuts merge and the small part's edge is cut away)."""
    g = clone(g)
    hosts = [(p, i) for p in g.parts for i in p.inner if i.area > 20000]
    rng.shuffle(hosts)
    for p, i in hosts:
        smalls = [q for q in g.parts if q is not p and q.outer.area < 0.5 * i.area and q.outer.area > 1500]
        rng.shuffle(smalls)
        for q in smalls[:10]:
            ci, cq = i.centroid, q.outer.centroid
            dx, dy = ci.x - cq.x, ci.y - cq.y
            o = affinity.translate(q.outer, dx, dy)
            if not o.within(i): continue
            # slide toward the cut-out edge until 1.5 mm is left
            a, b = nearest_points(o.exterior, i.exterior)
            d = a.distance(b)
            if d < 1.5: continue
            k = (d - 1.5) / d
            ddx, ddy = dx + (b.x - a.x) * k, dy + (b.y - a.y) * k
            o2 = affinity.translate(q.outer, ddx, ddy)
            if not o2.within(i) or i.exterior.distance(o2) < 1.3: continue
            if any(o2.intersects(r.outer) for r in g.parts if r is not q and r is not p): continue
            q.outer = o2
            moved = {id(x): affinity.translate(x, ddx, ddy) for x in q.inner}
            for f in q.features:
                if f.geom is None: continue
                f.geom = moved[id(f.geom)] if id(f.geom) in moved else affinity.translate(f.geom, ddx, ddy)
            q.inner = [moved[id(x)] for x in q.inner]
            return g
    return None


FAULTS += [
    Mut('gm93', 'One of two identical parts drawn 0.75 mm fat all round (tool offset baked into that copy only)',
        'CAM offsets every outline by the cutter radius; a copy whose geometry already carries an offset (an offset '
        'command applied to the wrong copy, or a part re-exported from a toolpath) is cut 1.5 mm too wide and long, '
        'with slots and holes 1.5 mm too small: its joints do not go together while its twin\'s do',
        _k_twin_fat,
        source='Vectric / Fusion 360 CAM docs (tool compensation is applied by the toolpath; geometry must be drawn at '
               'finished size); ShopBot forum threads on parts cut oversize after an offset was drawn into the file; '
               'Opendesk making guide (cut a test piece and check the fit of every part type)'),
    Mut('gm94', 'One through slot / cut-out on one of two identical parts drawn 5 mm to one side of where its twin has it',
        'Paired parts take the same tabs, rails or mating sheets: a slot nudged 5 mm on one copy no longer lines up with '
        'the tab that goes through it, so the frame cannot be assembled square, or the joint is forced and splits',
        _k_twin_slot_shift,
        source='Opendesk / WikiHouse making notes (paired parts must match; test-assemble a pair); CAD forum threads on '
               'objects nudged by arrow keys / snap after copying; Fab Academy press-fit assignments (misplaced slots '
               'the commonest assembly failure)'),
    Mut('gm95', 'A small part nested inside another part\'s cut-out only 1.5 mm from the cut-out edge (part-in-part)',
        'Nesting small parts in the waste of a big cut-out saves sheet, but the gap must exceed the cutter diameter: '
        'with 1.5 mm left, the 6 mm bit cutting the cut-out also cuts away the small part\'s edge (or the two cuts merge '
        'and the small part comes loose unheld and is thrown)',
        _k_part_in_hole_tight,
        source='Vectric / Fusion 360 nesting settings (part gap at least the tool diameter, part-in-part nesting option); '
               'ShopBot "Holding Down Material for Cutting" (small parts loose in the cut are thrown); CNC forum '
               'threads on nested parts damaged by a neighbouring cut'),
]
