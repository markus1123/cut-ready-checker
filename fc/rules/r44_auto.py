"""R44 dimension chains close with their physical allowance.

Shared cause: almost every size in a flat-pack job is DERIVED - it is a neighbour's size plus or minus a physical
allowance: saw kerf between dealer pieces, the play a drawer bottom keeps in its groove, the 90 degree corners that make
a part's outline the L x B the joints assume, the lip of the top past the drawer fronts. When an allowance is entered as
0, typed 10x, halved by a code bug, or lost in an export/CAD edit, every individual number still looks plausible, but the
chain no longer closes against the real material: a part runs off its offcut, a box does not close, a carcass racks,
a top becomes a lever. This rule recomputes each chain from what leaves the house (DXF files, cut list, 3D model) and
requires the allowance to lie in its physical range.

(a) Saw kerf. Sheets larger than the machine bed are split by the dealer's panel saw. Every sheet file's size must fit
    into a piece of the board's catalogue format after real kerfs: each sheet file is one dealer piece, so its size
    must equal (+-1 mm) a piece the saw can cut from the format with kerf = max(entered, KERF_MIN). Panel/beam saw main blades cut 3.2-4.4 mm
    (Striebig/Holzma/Altendorf blade data; scoring blade adds width, never removes it), so KERF_MIN = 3.0 mm.
    The entered kerf itself must lie in [KERF_MIN, KERF_MAX = 6 mm]: no dealer saw blade is wider; a larger number is a
    typing slip and makes the dealer's cut instructions (piece sizes) wrong.
(b) Square outlines. Every outer contour (main sheets and test kit) must be built of axis-parallel edges: parts are
    nested at 0/90 degrees only, so a sloping edge is a moved/snapped vertex. Tolerance SQUARE_TOL = 0.3 mm deviation
    over the edge. Cabinetmaking practice accepts <= 1 mm diagonal difference on an assembled carcass (1/32 in); the
    drawn file is exact by construction, so even 0.3 mm of drawn skew uses a third of that budget before any
    machine/assembly error.
(c) Drawer bottom in its groove. For each assembled drawer, the bottom's penetration into each side/end (3D model) must
    be <= the groove depth actually cut (min of part model and the Z code on the DXF groove layer) minus MIN_PLAY = 0.2
    mm, and >= MIN_ENGAGE = 4 mm. Why: HDF is rigid - if it bottoms out in a shallow groove the box cannot be pulled
    shut and the confirmats/glue lines open; 0.2 mm covers the +-0.1-0.2 mm CNC/board size tolerance. Below 4 mm of
    engagement a loaded 6 mm bottom (sag ~L/100) slips out (common practice: groove 1/3-1/2 of a 16-19 mm side, i.e.
    6-9 mm, bottom engaged to within 0.5-1 mm of it). The bottom's thickness band must also lie inside the groove
    width with >= MIN_PLAY total play (groove = panel + 0.5 mm is Blum/Hettich practice).
(d) Top lip. The top's front edge may project at most LIP_MAX = 40 mm past the drawer front faces, and must not stop
    behind the carcass front (it would leave the sides' front edges and joints uncovered). Workshop practice for chest
    tops is a 0-25 mm lip; past ~40 mm an unsupported 19 mm board deflects and becomes the lever in the tip-over load
    case (EN 14749 / ASTM F2057: vertical load near the front edge, the chest pivots on its front legs).
"""
import re
import nestlib
from fc.core import rule, Finding

KERF_MIN, KERF_MAX = 3.0, 6.0
SQUARE_TOL = 0.3
MIN_PLAY, MIN_ENGAGE = 0.2, 4.0
LIP_MAX = 40.0
CUT = '10_KONTUR'


def _inside(pt, pts):
    x, y, c = pt[0], pt[1], False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _outer(sh):
    return [e for e in sh['ents'] if e['type'] == 'POLYLINE' and e.get('layer', '').startswith(CUT)
            and 'INNVENDIG' not in e['layer'] and len(e['pts']) >= 3]


def _code_of(sh, contour):
    for t in sh['ents']:
        if t['type'] == 'TEXT' and t.get('text') and 'x' in t and _inside((t['x'], t['y']), contour['pts']):
            return t['text'].split(' ')[0]
    return None


def _kerf(d):
    out = []
    PL, V = d.P['plater'], d.P['verksted']
    k = PL.get('sagsnitt')
    if k is None or not (KERF_MIN <= k <= KERF_MAX):
        out.append(Finding('R44', 'error', 'Panel-saw kerf (plater.sagsnitt) is %s mm; real dealer saw blades cut %g-%g mm. '
                           'The sheet pieces ordered from the dealer do not match what the saw leaves.' % (k, KERF_MIN, KERF_MAX)))
    fmt = {m['id']: m['format'] for m in d.P.get('_valg', {}).values() if m.get('format')}
    keff = max(k or 0, KERF_MIN)
    for sh in d.sheets:
        m = re.match(r'^[a-z]+\d+_(.+)_\d+x\d+\.dxf$', sh['file'])
        if not m or m.group(1) not in fmt or not sh['W']:
            continue
        pieces = nestlib.split_sheet(fmt[m.group(1)], V['plate_maks'], keff, PL.get('min_bit', 0))
        w, h = sh['W'], sh['H']
        # each sheet file IS one dealer piece (the nest is made on it), so its size must be one the saw can produce
        if not any((abs(w - a) <= 1 and abs(h - b) <= 1) or (abs(w - b) <= 1 and abs(h - a) <= 1) for a, b in pieces):
            out.append(Finding('R44', 'error', '%s: a %dx%d piece cannot come out of a %s sheet once the saw has taken '
                               '>= %g mm per cut (pieces possible: %s); parts at its far edge run off the board.'
                               % (sh['file'], w, h, 'x'.join('%g' % v for v in fmt[m.group(1)]), KERF_MIN,
                                  ', '.join('%gx%g' % tuple(p) for p in pieces))))
    return out


def _square(d):
    out = []
    for sh in list(d.sheets) + list(getattr(d, 'kit_sheets', [])):
        for c in _outer(sh):
            P = [p for p in c['pts'] if p[0] is not None]
            if len(P) > 1 and abs(P[0][0] - P[-1][0]) < 1e-6 and abs(P[0][1] - P[-1][1]) < 1e-6:
                P = P[:-1]
            for (x1, y1), (x2, y2) in zip(P, P[1:] + P[:1]):
                dx, dy = abs(x2 - x1), abs(y2 - y1)
                if min(dx, dy) > SQUARE_TOL:
                    code = _code_of(sh, c) or '?'
                    out.append(Finding('R44', 'error', '%s: outline of %s has an edge %.1f mm out of square (from (%.1f, %.1f) '
                                       'to (%.1f, %.1f)); the part comes out a trapezoid and the carcass racks.'
                                       % (sh['file'], code, min(dx, dy), x1, y1, x2, y2), code))
                    break
    return out


def _dxf_groove_depth(d):
    """{part code: min groove Z read from the DXF groove layers inside that part's outline}."""
    res = {}
    for sh in d.sheets:
        outer = _outer(sh)
        for g in sh['ents']:
            if g['type'] != 'POLYLINE' or not g.get('layer', '').startswith('04_'):
                continue
            mz = re.search(r'_Z(\d+(?:P\d+)?)', g['layer'])
            if not mz:
                continue
            z = float(mz.group(1).replace('P', '.'))
            pts = [p for p in g['pts'] if p[0] is not None]
            c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            for o in outer:
                if _inside(c, o['pts']):
                    code = _code_of(sh, o)
                    if code:
                        res[code] = min(res.get(code, z), z)
                    break
    return res


def _bottom_fit(d):
    out, seen = [], set()
    dxf_z = _dxf_groove_depth(d)
    grooves = {}
    for p in d.parts:
        gs = [o for o in p['ops'] if o['kind'] == 'groove']
        if gs:
            grooves[p['code']] = gs
    tb = d.info.get('tb')
    by_label = {a['label']: a for a in d.asm}
    for sb in d.asm:
        if sb['code'] != 'SB':
            continue
        tag = sb['label'].split(' ', 1)[1] if ' ' in sb['label'] else ''
        x, y, z, dx, dy, dz = sb['b']
        for code in ('S', 'SH', 'E1', 'E2'):
            a = by_label.get('%s %s' % (code, tag))
            if not a:
                continue
            ax, ay, az, adx, ady, adz = a['b']
            # penetration along the side's thickness axis (x for S/SH, y for E1/E2)
            if code in ('S', 'SH'):
                pen = min(x + dx, ax + adx) - max(x, ax)
            else:
                pen = min(y + dy, ay + ady) - max(y, ay)
            if pen <= 0.05:
                continue
            key = code
            if key in seen:
                continue
            gs = grooves.get(code)
            if not gs:
                seen.add(key)
                out.append(Finding('R44', 'error', 'Drawer %s: bottom reaches %.1f mm into %s, but %s has no groove; the box '
                                   'cannot be closed.' % (tag, pen, code, code), code))
                continue
            depth = min(float(o['z']) for o in gs)
            if code in dxf_z:
                depth = min(depth, dxf_z[code])
            msg = None
            if pen > depth - MIN_PLAY:
                msg = ('bottom reaches %.1f mm into %s but the groove is cut only %.1f mm deep (need >= %.1f mm play); the '
                       'bottom bottoms out and the box will not close by %.1f mm per side'
                       % (pen, code, depth, MIN_PLAY, pen - depth + MIN_PLAY))
            elif pen < MIN_ENGAGE:
                msg = ('bottom engages only %.1f mm in the %s groove (need >= %g mm); a loaded bottom slips out'
                       % (pen, code, MIN_ENGAGE))
            else:
                # thickness band of the bottom inside the groove's width band (part y measured from the bottom edge)
                lo, hi = az + min(min(o['y1'], o['y2']) for o in gs), az + max(max(o['y1'], o['y2']) for o in gs)
                band = [(az + min(o['y1'], o['y2']), az + max(o['y1'], o['y2'])) for o in gs]
                t = dz if tb is None else tb
                ok = any(g1 - 0.05 <= z and z + t <= g2 + 0.05 and (g2 - g1) - t >= MIN_PLAY - 1e-6 for g1, g2 in band)
                if not ok:
                    msg = ('the %.1f mm bottom at height %.1f-%.1f does not sit in the %s groove (%.1f-%.1f) with >= %.1f mm play'
                           % (t, z - az, z + t - az, code, lo - az, hi - az, MIN_PLAY))
            if msg:
                seen.add(key)
                out.append(Finding('R44', 'error', 'Drawer %s: %s.' % (tag, msg), code))
    return out


def _top_lip(d):
    out = []
    A = [a for a in d.asm if a['code'] == 'A']
    K = [a for a in d.asm if a['code'] == 'K']
    C = [a for a in d.asm if a['code'] in ('C', 'CH')]
    if not A:
        return out
    ty = min(a['b'][1] for a in A)
    if K:
        fy = min(a['b'][1] for a in K)
        lip = fy - ty
        if lip > LIP_MAX:
            out.append(Finding('R44', 'error', 'Top projects %.0f mm past the drawer fronts (max %g mm): an unsupported lever '
                               'in front of the front legs - tip-over risk and a wasted oversize top.' % (lip, LIP_MAX), 'A'))
    if C:
        cy = min(a['b'][1] for a in C)
        if ty > cy + 0.5:
            out.append(Finding('R44', 'error', 'Top front edge stops %.1f mm behind the carcass front; the sides\' front edges '
                               'and joints are left uncovered.' % (ty - cy), 'A'))
    return out


@rule('R44', 'Dimension chains close with physical allowances: saw kerf, square outlines, bottom-in-groove play, top lip')
def chains(d):
    return _kerf(d) + _square(d) + _bottom_fit(d) + _top_lip(d)
