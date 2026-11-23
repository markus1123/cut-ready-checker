"""R42 machine work envelope: every toolpath in the cutting files must lie inside the space the router can
physically reach and the stock can absorb, in all three axes. A job that leaves that envelope is a crash or a ruined
bit, however correct the furniture geometry is.

Shared cause: a machine-limit number (bed size, sheet size, cut depth) is wrong in the input or gets corrupted on
the way into the file. The checker does not trust the design's own `verksted.plate_maks` for this. It
checks the files against the physical machine:

X/Y: the workshop router is a ShopBot PRSalpha 96x48 (Fellesverkstedet). Its spoilboard and hold-down are laid out
    for a 4x8 ft sheet, 2440 x 1220 mm (US 4x8 = 2438 x 1219 fits too). The extra gantry travel past that is
    overtravel for the tool radius, not clampable bed. So:
      - the machine-size parameter must not be larger than the bed,
      - every sheet file (its declared size) must fit on the bed, in either orientation,
      - every entity (outline vertex, circle edge, label) must lie within the bed.
    Tolerance 0.5 mm (DXF rounding).
Z:  no layer may ask for a depth greater than the board on that sheet + 1.0 mm. Workshop practice (ShopBot's
    spoilboard guidance and common CNC practice) is to cut through by 0.2-0.5 mm into the MDF spoilboard. More than
    ~1 mm ruins the spoilboard, and a depth several mm past the board means the bit plunges into the table/vacuum
    plenum. As an absolute cap, no depth may exceed the longest flute in the workshop (the bit's cutting length),
    whatever the board.
"""
from fc.core import rule, Finding
from fc.dxfread import layer_num

BED = (2440.0, 1220.0)    # ShopBot PRSalpha 96x48 clampable bed (4x8 ft sheet)
TOL = 0.5                 # mm, DXF coordinate rounding
SPOIL = 1.0               # mm, max cut-through into the spoilboard


def _fits(w, h):
    a, b = max(w, h), min(w, h)
    return a <= BED[0] + TOL and b <= BED[1] + TOL


def _extent(sh):
    xs, ys = [], []
    for e in sh['ents']:
        if e['type'] == 'POLYLINE':
            xs += [p[0] for p in e['pts'] if p[0] is not None]
            ys += [p[1] for p in e['pts'] if p[1] is not None]
        elif e['type'] == 'CIRCLE' and 'x' in e:
            r = e.get('r', 0)
            xs += [e['x'] - r, e['x'] + r]; ys += [e['y'] - r, e['y'] + r]
        elif e['type'] == 'TEXT' and 'x' in e:
            xs.append(e['x']); ys.append(e['y'])
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


@rule('R42', 'Machine work envelope: everything fits the router bed (2440x1220) and no cut goes more than 1 mm past the board')
def envelope(d):
    out = []
    V = d.P.get('verksted', {})
    pm = V.get('plate_maks')
    if pm and len(pm) == 2 and not _fits(float(pm[0]), float(pm[1])):
        out.append(Finding('R42', 'error', 'Machine size entered as %gx%g mm, but the router bed is %gx%g; '
                           'parts nested into the extra area cannot be reached or clamped.' % (pm[0], pm[1], BED[0], BED[1])))
    thk = {s['plate']: s.get('tykkelse') for s in d.summary.get('plater', [])}
    tm = [v for v in d.P.get('tykkelse_malt', {}).values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    t_max = max(tm) if tm else None
    flutes = [V.get(k) for k in ('fres_liten_skjaerlengde', 'fres_stor_skjaerlengde') if isinstance(V.get(k), (int, float))]
    flute = max(flutes) if flutes else None
    for sh in list(d.sheets) + list(getattr(d, 'kit_sheets', [])):
        f = sh['file']
        if sh.get('W') and sh.get('H') and not _fits(sh['W'], sh['H']):
            out.append(Finding('R42', 'error', '%s: sheet is %dx%d mm and does not fit the %gx%g router bed.'
                               % (f, sh['W'], sh['H'], BED[0], BED[1])))
        ext = _extent(sh)
        if ext:
            x0, y0, x1, y1 = ext
            if x0 < -TOL or y0 < -TOL or not _fits(x1, y1):
                out.append(Finding('R42', 'error', '%s: toolpaths reach (%.0f, %.0f), outside the %gx%g router bed.'
                                   % (f, x1, y1, BED[0], BED[1])))
        t = thk.get(f) or t_max
        seen = set()
        for e in sh['ents']:
            L = e.get('layer', '')
            if L in seen:
                continue
            seen.add(L)
            z = layer_num(L, 'Z')
            if z is None:
                continue
            if t and z > t + SPOIL + 1e-6:
                out.append(Finding('R42', 'error', '%s: layer %s cuts %g mm deep in a %.2f mm board, %.1f mm into the '
                                   'spoilboard/table (max %g mm).' % (f, L, z, t, z - t, SPOIL)))
            elif flute and z > flute + 1e-6:
                out.append(Finding('R42', 'error', '%s: layer %s cuts %g mm deep, more than the longest bit flute (%g mm).'
                                   % (f, L, z, flute)))
    return out
