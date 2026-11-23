"""Small 3D helpers shared by the general rules."""


def seg_dist(p1, q1, p2, q2):
    """Minimum distance between segments p1-q1 and p2-q2 (3D)."""
    import math
    d1 = [b - a for a, b in zip(p1, q1)]; d2 = [b - a for a, b in zip(p2, q2)]; r = [a - b for a, b in zip(p1, p2)]
    dot = lambda u, v: sum(x * y for x, y in zip(u, v))
    a, e, f = dot(d1, d1), dot(d2, d2), dot(d2, r)
    if a < 1e-9 and e < 1e-9:
        return math.dist(p1, p2)
    if a < 1e-9:
        s, t = 0.0, min(1, max(0, f / e))
    else:
        c = dot(d1, r)
        if e < 1e-9:
            t, s = 0.0, min(1, max(0, -c / a))
        else:
            b = dot(d1, d2); den = a * e - b * b
            s = min(1, max(0, (b * f - c * e) / den)) if den > 1e-9 else 0.0
            t = (b * s + f) / e
            if t < 0:
                t, s = 0.0, min(1, max(0, -c / a))
            elif t > 1:
                t, s = 1.0, min(1, max(0, (b - c) / a))
    c1 = [p + d * s for p, d in zip(p1, d1)]; c2 = [p + d * t for p, d in zip(p2, d2)]
    return math.dist(c1, c2)


def box_overlap(a, b):
    """Overlap depth along each axis of two boxes (x, y, z, dx, dy, dz); negative = gap."""
    return [min(a[i] + a[i + 3], b[i] + b[i + 3]) - max(a[i], b[i]) for i in range(3)]
