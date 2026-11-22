"""No edge band on a joint edge: an edge that another panel sits against, or that is drilled for a joint."""
from fc.core import rule, Finding
from fc.world import frames, neg, dot
from fc.rules.r06_bands import band_edges

MIN_CONTACT = 100.0   # mm^2 of flush contact before an edge counts as a mating (joint) edge
FLUSH = 0.3           # mm: edge face and neighbouring panel face count as touching within this gap
EDGE_OP = {'venstre ende': 'x0', 'høyre ende': 'xL', 'underkant': 'y0', 'overkant': 'yB'}
LOOSE = ('K',)        # fronts hang on the drawer with a gap to the carcass; they are not joined to its edges


def _edge_box(f, e):
    """World box (x0, x1, y0, y1, z0, z1) of the edge face e, and its outward axis/sign."""
    x, y, z, dx, dy, dz = f['box']
    v = {'x0': neg(f['ex']), 'xL': f['ex'], 'y0': neg(f['ey']), 'yB': f['ey']}[e]
    ax = max(range(3), key=lambda i: abs(v[i]))
    lo, hi = [x, y, z], [x + dx, y + dy, z + dz]
    plane = hi[ax] if v[ax] > 0 else lo[ax]
    return lo, hi, ax, (1 if v[ax] > 0 else -1), plane


def _contact(f, e, others):
    lo, hi, ax, sgn, plane = _edge_box(f, e)
    hits = []
    for g in others:
        if g is f or g['code'] in LOOSE:
            continue
        x, y, z, dx, dy, dz = g['box']
        glo, ghi = [x, y, z], [x + dx, y + dy, z + dz]
        near = glo[ax] if sgn > 0 else ghi[ax]          # the neighbour's face pointing back at our edge
        if abs(near - plane) > FLUSH:
            continue
        area = 1.0
        for i in range(3):
            if i != ax:
                area *= max(0.0, min(hi[i], ghi[i]) - max(lo[i], glo[i]))
        if area >= MIN_CONTACT:
            hits.append('%s (%s)' % (g['code'], g['label']))
    return hits


@rule('R17', 'Edges that are joined (another panel sits on them, or they carry edge bores) must not be edge-banded')
def check(d):
    """Workshop reason: edge band (ABS/veneer, 0.5-2 mm) is for free, visible edges only. Banding an edge that another
    panel sits on or is fastened to adds the band thickness to the part (a banded side stands 1-2 mm taller than the
    unbanded middle wall, so the top rocks or gaps and the carcass is out of square), and the Minifix bolt / dowel
    holes in that edge are then drilled through the band, which chips, tears loose and pulls the hole off centre.
    Unless the cut size is reduced by the band thickness AND the joint holes are placed for the band, a banded joint
    edge is a cutting-list error. An edge is a joint edge if the part has edge bores ('kant:<edge>') on it, or if in
    the assembled 3D model another (non-front) panel lies flush against that edge face over >= MIN_CONTACT mm^2."""
    fr = [f for f in frames(d) if f['code'] not in LOOSE]
    out, seen = [], set()
    for f in fr:
        p = f['part']
        banded = band_edges(p)
        if not banded:
            continue
        bored = {EDGE_OP[o['face'].split(':', 1)[1]] for o in p['ops']
                 if o['kind'] == 'edge' and o['face'].split(':', 1)[-1] in EDGE_OP}
        for e in sorted(banded):
            why = []
            if e in bored:
                why.append('it carries edge bores (Minifix/dowel)')
            hits = _contact(f, e, fr)
            if hits:
                why.append('it sits flush against %s' % ', '.join(sorted(set(hits))[:3]))
            key = (p['code'], e)
            if why and key not in seen:
                seen.add(key)
                out.append(Finding('R17', 'error',
                                   '%s (%s): edge %s is banded but is a joint edge - %s. The band makes the part '
                                   'too long/tall at the joint and the edge holes get drilled through the band. '
                                   'Remove the band (or shorten the part by the band thickness and re-place the holes).'
                                   % (p['code'], f['label'], e, '; '.join(why)), p['code']))
    return out
