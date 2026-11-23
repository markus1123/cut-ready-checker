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
]
