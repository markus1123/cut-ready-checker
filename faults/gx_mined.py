"""Mined fault TYPES (documented real-world CNC flat-pack failures) applied to real, built designs (train split).
Same format as faults/gx_train.py. The loop's agents may read this file."""
import math
from shapely import affinity
from shapely.geometry import Point, Polygon
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
]
