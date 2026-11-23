"""Seeded fault TYPES applied to real, built designs (train split). The loop's agents may read this file."""
import random
from shapely import affinity
from shapely.geometry import Point, Polygon, LineString
from fc.gx.mutate import Mut, clone, holes, biggest, move_to_gap


def _open_outline(g, rng):
    g = clone(g); p = rng.choice(biggest(g, 5))
    pts = list(p.outer.exterior.coords)
    if len(pts) < 5: return None
    i = rng.randrange(len(pts) - 2)
    line = LineString(pts[i + 1:] + pts[1:i + 1])      # drop the segment i -> i+1: a gap in the outline
    g.parts.remove(p); g.open_chains.append((line, p.layer))
    return g


def _overlap(g, rng):
    if len(g.parts) < 2: return None
    g = clone(g); a = rng.choice(biggest(g, 6))
    others = [p for p in g.parts if p is not a]
    b = min(others, key=lambda p: p.outer.distance(a.outer))
    dx = (b.outer.centroid.x - a.outer.centroid.x) * 0.25; dy = (b.outer.centroid.y - a.outer.centroid.y) * 0.25
    for att in ('outer',):
        a.outer = affinity.translate(a.outer, dx, dy)
    a.inner = [affinity.translate(i, dx, dy) for i in a.inner]
    for f in a.features: f.geom = affinity.translate(f.geom, dx, dy)
    if a.outer.intersection(b.outer).area < 1: return None
    return g


def _oversize(g, rng):
    g = clone(g); p = biggest(g)[0]
    minx, miny, maxx, maxy = p.outer.bounds
    k = 3200.0 / max(maxx - minx, maxy - miny)
    if k < 1.05: return None
    c = p.outer.centroid
    p.outer = affinity.scale(p.outer, k, k, origin=c)
    p.inner = [affinity.scale(i, k, k, origin=c) for i in p.inner]
    for f in p.features: f.geom = affinity.scale(f.geom, k, k, origin=c)
    return g


def _hole_edge(g, rng):
    g = clone(g)
    cand = [(p, f) for p in g.parts for f in holes(p) if f.geom in p.inner]     # through holes
    if not cand: return None
    p, f = rng.choice(cand)
    m = move_to_gap(p, f.geom, 0.8)
    if m is None: return None
    if f.geom in p.inner: p.inner[p.inner.index(f.geom)] = m
    f.geom = m
    return g


def _unit_small(g, rng):
    g = clone(g); k = 1 / 25.4
    for p in g.parts:
        p.outer = affinity.scale(p.outer, k, k, origin=(0, 0)); p.inner = [affinity.scale(i, k, k, origin=(0, 0)) for i in p.inner]
        for f in p.features:
            f.geom = affinity.scale(f.geom, k, k, origin=(0, 0)); f.r = f.r * k if f.r else f.r
    return g


def _tiny_hole(g, rng):
    g = clone(g)
    cand = [(p, f) for p in g.parts for f in holes(p) if f.geom in p.inner]
    if not cand: return None
    p, f = rng.choice(cand)
    c = f.geom.centroid; m = Point(c.x, c.y).buffer(1.25, 32)     # 2.5 mm through hole: smaller than any furniture bit
    p.inner[p.inner.index(f.geom)] = m; f.geom = m; f.r = 1.25
    return g


def _thin_web(g, rng):
    g = clone(g)
    cand = [(p, i) for p in g.parts for i in p.inner if i.area > 200 and p.outer.exterior.distance(i) > 8]
    if not cand: return None
    p, i = rng.choice(cand)
    m = move_to_gap(p, i, 1.5)
    if m is None or not m.within(p.outer): return None
    p.inner[p.inner.index(i)] = m
    for f in p.features:
        if f.geom is i: f.geom = m
    return g


def _kerf_twice(g, rng):
    g = clone(g)
    for p in g.parts:
        p.outer = p.outer.buffer(0.75, join_style=2)
        p.inner = [i.buffer(-0.75, join_style=2) for i in p.inner]
        p.inner = [i for i in p.inner if not i.is_empty and i.geom_type == 'Polygon']
    return g


def _pocket_through(g, rng):
    if not g.thickness: return None
    g = clone(g)
    cand = [f for p in g.parts for f in p.features if f.op == 'pocket' and f.depth and f.depth < g.thickness]
    if not cand: return None
    f = rng.choice(cand); f.depth = g.thickness + 0.5
    return g


FAULTS = [
    Mut('gt01', 'Part outline has a gap (export did not join the contour)', 'CAM cannot make a closed cut; the part is not cut out or the tool goes the wrong way', _open_outline),
    Mut('gt02', 'Two parts overlap on the sheet', 'Cutting one destroys the other', _overlap),
    Mut('gt03', 'A part is bigger than a 2500x1250 sheet', 'Cannot be cut from stock sheets at all', _oversize),
    Mut('gt04', 'Through hole 0.8 mm from the part edge', 'Edge blows out when drilled or loaded', _hole_edge),
    Mut('gt05', 'Whole drawing 25.4x too small (inch/mm mix-up)', 'Parts come out at toy size; whole sheet wasted', _unit_small),
    Mut('gt06', 'Through hole 2.5 mm diameter', 'Smaller than any furniture router bit; cannot be cut, or the bit snaps', _tiny_hole),
    Mut('gt07', 'Opening 1.5 mm from the part edge (thin web)', 'Web breaks during cutting or in use', _thin_web),
    Mut('gt08', 'Tool compensation applied twice (parts 0.75 mm fat all round)', 'Slots 1.5 mm too narrow, tabs too wide: joints do not go together', _kerf_twice),
    Mut('gt09', 'Pocket deeper than the sheet', 'Pocket cuts through and the part falls apart', _pocket_through),
]
