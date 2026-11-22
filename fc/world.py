"""Place every part instance in 3D with a full frame, so holes can be followed across joints.

This is the checker's OWN statement of how the kommode is assembled (an oracle written independently of
the generator's hole code): for each part code, which face F1 points to and which way the part's x/y axes run.
World: X = right (seen from the front), Y = back (0 = carcass front), Z = up (0 = underside of carcass).

Frame: origin O = part (0,0) on the F1 surface, ex/ey = world directions of part +x/+y, n = F1 outward normal.
A physical (rigid) part needs ex x ey == n. If not, the instance is the MIRROR image of the part as cut.
"""
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)


def neg(v): return tuple(-a for a in v)
def add(a, b): return tuple(p + q for p, q in zip(a, b))
def mul(v, s): return tuple(a * s for a in v)
def dot(a, b): return sum(p * q for p, q in zip(a, b))
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def frames(d):
    """List of instances: dict(code, label, part, O, ex, ey, n, box)."""
    parts = {p['code']: p for p in d.parts}
    inst = []
    W = d.info['W']
    for a in d.asm:
        code, (x, y, z, dx, dy, dz) = a['code'], a['b']
        p = parts.get(code)
        if p is None:
            continue
        lab = a['label']
        if code == 'A':        # top: F1 = underside, x from left end, y from front edge
            f = dict(O=(x, y, z), ex=X, ey=Y, n=neg(Z))
        elif code in ('C', 'CH', 'S', 'SH', 'D'):
            # vertical parts, y from the bottom. Which way F1 faces: sides/drawer sides face into their opening;
            # the middle wall faces the way its F1 label says. x runs from the edge named in xref.
            if code == 'D':
                into_x = 'venstre' not in p['faces'].get('F1', '').lower()
            elif code in ('C', 'CH'):
                into_x = x < W / 2
            else:
                mate = [b for b in d.asm if b['code'] == 'E1' and b['label'].split()[-1] == lab.split()[-1]]
                into_x = bool(mate) and x < mate[0]['b'][0]
            n = X if into_x else neg(X)
            sx = x + dx if into_x else x
            if p['xref'].startswith('bakkant'):
                f = dict(O=(sx, y + dy, z), ex=neg(Y), ey=Z, n=n)
            else:
                f = dict(O=(sx, y, z), ex=Y, ey=Z, n=n)
        elif code == 'B':      # bottom: F1 = top face
            f = dict(O=(x, y, z + dz), ex=X, ey=Y, n=Z)
        elif code == 'H':      # plinth strip on edge, x from left end, y from bottom edge; F1 = front face
            f = dict(O=(x, y, z), ex=X, ey=Z, n=neg(Y))
        elif code == 'K':      # fronts: F1 = visible face
            f = dict(O=(x, y, z), ex=X, ey=Z, n=neg(Y))
        elif code == 'S':      # drawer sides: F1 = inside of the box, x from front, y from bottom
            # left or right side of its box: compare with the E1 of the same drawer
            mate = [b for b in d.asm if b['code'] == 'E1' and b['label'].split()[-1] == lab.split()[-1]]
            left = mate and x < mate[0]['b'][0]
            f = dict(O=(x + dx, y, z), ex=Y, ey=Z, n=X) if left else dict(O=(x, y, z), ex=Y, ey=Z, n=neg(X))
        elif code == 'E1':     # front end: F1 = inside of the box (faces +Y)
            f = dict(O=(x, y + dy, z), ex=X, ey=Z, n=Y)
        elif code == 'E2':     # back end: F1 = inside (faces -Y)
            f = dict(O=(x, y, z), ex=X, ey=Z, n=neg(Y))
        else:
            continue
        f.update(code=code, label=lab, part=p, box=(x, y, z, dx, dy, dz))
        inst.append(f)
    return inst


def proper(f):
    return dot(cross(f['ex'], f['ey']), f['n']) > 0


def to_world(f, px, py, depth=0.0):
    """Part point (px, py) on F1, `depth` mm into the board (F2 surface = depth t)."""
    return add(add(add(f['O'], mul(f['ex'], px)), mul(f['ey'], py)), mul(f['n'], -depth))


def holes(f):
    """World holes of an instance: list of dict(entry, dir (into the material), d, depth, op, end)."""
    p, t = f['part'], f['part']['t']
    L, B = p['L'], p['B']
    out = []
    for o in p['ops']:
        k = o['kind']
        if k in ('groove', 'manual'):
            continue
        if k == 'edge':
            e, pos = o['face'], float(o['pos'])
            if e.endswith('venstre ende'):
                P0, dv = to_world(f, 0, pos, t / 2), f['ex']
            elif e.endswith('høyre ende'):
                P0, dv = to_world(f, L, pos, t / 2), neg(f['ex'])
            elif e.endswith('underkant'):
                P0, dv = to_world(f, pos, 0, t / 2), f['ey']
            elif e.endswith('overkant'):
                P0, dv = to_world(f, pos, B, t / 2), neg(f['ey'])
            else:
                continue
            out.append(dict(entry=P0, dir=dv, d=o['d'], depth=o['z'], op=o, end='edge'))
            continue
        x, y = o['x'], o['y']
        if k == 'through':
            out.append(dict(entry=to_world(f, x, y, 0), dir=neg(f['n']), d=o['d'], depth=t, op=o, end='F1'))
            out.append(dict(entry=to_world(f, x, y, t), dir=f['n'], d=o['d'], depth=t, op=o, end='F2'))
        elif o['face'] == 'F1':
            out.append(dict(entry=to_world(f, x, y, 0), dir=neg(f['n']), d=o['d'], depth=o['z'], op=o, end='F1'))
        else:
            out.append(dict(entry=to_world(f, x, y, t), dir=f['n'], d=o['d'], depth=o['z'], op=o, end='F2'))
    return out


def inside(box, pt, eps=0.05):
    x, y, z, dx, dy, dz = box
    return x + eps < pt[0] < x + dx - eps and y + eps < pt[1] < y + dy - eps and z + eps < pt[2] < z + dz - eps
