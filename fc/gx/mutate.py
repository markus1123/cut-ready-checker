"""Helpers for seeded faults on real designs. A fault type = Mut(id, title, why, fn) where
fn(g: GDesign, rng: random.Random) -> mutated copy of g, or None if this design has nothing to break that way.
Never mutate g in place: start from clone(g)."""
import copy, random
from dataclasses import dataclass
from typing import Callable
from shapely import affinity
from shapely.geometry import Polygon, Point, LineString


@dataclass
class Mut:
    id: str
    title: str
    why: str
    fn: Callable
    source: str = ''


def clone(g):
    return copy.deepcopy(g)


def holes(part, rmax=12.0):
    """Drilled / small round holes in a part: list of features with a radius."""
    return [f for f in part.features if f.op == 'hole' and f.r and f.r <= rmax]


def biggest(g, n=1):
    return sorted(g.parts, key=lambda p: -p.outer.area)[:n]


def edge_gap(part, geom):
    """Material left between geom (opening/hole) and the part's outer edge, mm."""
    return part.outer.exterior.distance(geom)


def move_to_gap(part, geom, gap):
    """Translate geom toward the nearest outer edge so `gap` mm of material remains."""
    from shapely.ops import nearest_points
    a, b = nearest_points(geom.boundary, part.outer.exterior)
    d = a.distance(b)
    if d < 1e-6: return None
    k = (d - gap) / d
    return affinity.translate(geom, (b.x - a.x) * k, (b.y - a.y) * k)
