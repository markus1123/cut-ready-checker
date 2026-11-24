"""The workshop's real machine and tools, so rules check a design against what is actually there instead of
against what the design's own params claim. Profiles live in fc/machines/<name>.json (built by
tools/machine_from_vtdb.py from the workshop's VCarve tool database + wiki). FC_MACHINE picks one."""
import json, os

NAME = os.environ.get('FC_MACHINE', 'fellesverkstedet')
M = json.load(open(os.path.join(os.path.dirname(__file__), 'machines', NAME + '.json'), encoding='utf-8'))
BED = tuple(M['bed'])
Z_MAX = M['z_max']
HOLD = M['holddown']


def endmills(material='wood'):
    return [b for b in M['bits'] if b['type'] == 'endmill' and b['material'] == material]


def bit(dia, tol=0.05, material='wood'):
    """The shop's end mill of this diameter (fastest setting if several), or None."""
    c = [b for b in endmills(material) if abs(b['d'] - dia) <= tol]
    return max(c, key=lambda b: b['feed_mm_min'] or 0) if c else None


def flute(dia):
    """(known flute length or None, lower bound from the shop's own depth per pass or None)."""
    b = bit(dia)
    return (b['flute_len'], b['flute_len_min']) if b else (None, None)


def circle_d(bit_d):
    """Hold-down circle diameter the shop asks for with this contour bit."""
    ks = sorted(HOLD['circle_d'], key=float)
    for k in ks:
        if bit_d <= float(k) + 0.5:   # a 1/4" (6.35) bit still takes the 6 mm circle
            return HOLD['circle_d'][k]
    return HOLD['circle_d'][ks[-1]]
