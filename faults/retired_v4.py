"""Blind held-out set h4: 25 fresh CNC flat-pack failure modes (8 params, 9 parts, 8 dxf).

Written against the generator only (kommode.py / nestlib.py / params.json / skinne.json). Every magnitude is derived
from the live params/parts/DXF where it matters, so the faults stay meaningful if the nominal design changes."""
import re
from fc.core import Fault
from faults.helpers import part


# ------------------------------------------------------------------------------------------- DXF utilities
def _pairs(text):
    lines = text.split('\n')
    if len(lines) % 2:
        lines = lines[:-1] if lines[-1] == '' else lines + ['']
    return [(lines[i], lines[i + 1]) for i in range(0, len(lines), 2)]


def _join(pairs):
    return '\n'.join(c + '\n' + v for c, v in pairs) + '\n'


def _split(text):
    """(head, [entity pair-lists], tail). A POLYLINE entity includes its VERTEXes and SEQEND."""
    p = _pairs(text)
    s = next(i for i in range(len(p)) if p[i] == ('2', 'ENTITIES')) + 1
    e = next(i for i in range(s, len(p)) if p[i] == ('0', 'ENDSEC'))
    ents, cur, in_poly = [], None, False
    for c, v in p[s:e]:
        if c == '0' and not (in_poly and v in ('VERTEX', 'SEQEND')):
            if cur:
                ents.append(cur)
            cur = []
            in_poly = v == 'POLYLINE'
        if c == '0' and v == 'SEQEND':
            in_poly = False
        cur.append((c, v))
    if cur:
        ents.append(cur)
    return p[:s], ents, p[e:]


def _build(head, ents, tail):
    return _join(head + [x for e in ents for x in e] + tail)


def _kind(e):
    return e[0][1]


def _layer(e):
    return next(v for c, v in e if c == '8')


def _labels(text):
    _, ents, _ = _split(text)
    return [next(v for c, v in e if c == '1') for e in ents if _kind(e) == 'TEXT']


def _sheet_with_label(files, code):
    """Sheet files carrying a part whose label starts with '<code> '."""
    return [k for k in sorted(files) if any(l.split(' ')[0] == code for l in _labels(files[k]))]


def _layers(text):
    _, ents, _ = _split(text)
    out = {}
    for e in ents:
        out[_layer(e)] = out.get(_layer(e), 0) + 1
    return out


def _num(tok):
    return float(tok.replace('P', '.'))


def _verts(e):
    out, x = [], None
    seen_vertex = False
    for c, v in e:
        if c == '0' and v == 'VERTEX':
            seen_vertex = True
        if seen_vertex and c == '10':
            x = float(v)
        if seen_vertex and c == '20':
            out.append((x, float(v)))
    return out


def _set_verts(e, pts):
    out, i, seen_vertex = [], -1, False
    for c, v in e:
        if c == '0' and v == 'VERTEX':
            seen_vertex = True; i += 1
        if seen_vertex and c == '10':
            v = '%.3f' % pts[i][0]
        if seen_vertex and c == '20':
            v = '%.3f' % pts[i][1]
        out.append((c, v))
    return out


def _rename_layer(text, old, new):
    return _join([(c, new if (c in ('8', '2') and v == old) else v) for c, v in _pairs(text)])


def _bit_d():
    from fc import design
    P, _ = design.base()
    return P['verksted']['fres_stor_d']


# ------------------------------------------------------------------------------------------- params faults
def p_kerf0(P, S):
    P['plater']['sagsnitt'] = 0


def p_reveal_neg(P, S):
    F = P['front']
    F['kant_topp_bunn'] = -max(abs(F['kant_topp_bunn']), 2)


def p_frontscrew_on_confirmat(P, S):
    D = P['skuff']
    ky = D['konfirmat_y'][0]
    ky = ky if ky >= 0 else D['hoyde'] + ky
    D['front_skrue_y'] = [ky] + list(D['front_skrue_y'][1:])
    D['front_skrue_x_inn'] = P['tykkelse_malt']['skuff']


def p_box_lower_than_slide(P, S):
    P['skuff']['hoyde'] = S['hoyde'] - 6


def p_rear_plinth_proud(P, S):
    K = P['korpus']
    K['bunnlist_y'] = list(K['bunnlist_y'][:-1]) + [P['ytre']['dybde_korpus'] - 10]


def p_overhang_x10(P, S):
    P['ytre']['topp_overheng_front'] = P['ytre']['topp_overheng_front'] * 10


def p_groove_mid_height(P, S):
    D = P['skuff']
    gw = P['tykkelse_malt']['skuffebunn'] + D['not_klaring']
    D['not_fra_underkant'] = round(D['hoyde'] / 2 - gw / 2, 1)


def p_depth_is_slide(P, S):
    P['ytre']['dybde_korpus'] = S['lengde']


# ------------------------------------------------------------------------------------------- parts faults
def q_spot_lost(parts, asm, info):
    for p in parts:
        for o in p['ops']:
            o.pop('cnc', None)


def q_sb_qty_rows(parts, asm, info):
    sb, k = part(parts, 'SB'), part(parts, 'K')
    sb['qty'] = max(1, k['qty'] // 2)


def q_no_middle_wall(parts, asm, info):
    part(parts, 'D')['qty'] = 0


def q_e2_no_groove(parts, asm, info):
    e2 = part(parts, 'E2')
    e2['ops'] = [o for o in e2['ops'] if o['kind'] != 'groove']


def q_top_inner_width(parts, asm, info):
    part(parts, 'A')['L'] = round(info['W'] - 2 * info['T'], 2)


def q_fronts_white(parts, asm, info):
    part(parts, 'K')['mat'] = 'korpus'


def q_top_wall_holes_bottom_coords(parts, asm, info):
    a = part(parts, 'A')
    xs = sorted({o['x'] for o in a['ops'] if 'x' in o})
    inner = set(xs[1:-1])
    for o in a['ops']:
        if o.get('x') in inner:
            o['x'] = round(o['x'] - info['T'], 2)


def q_bottom_no_side_bolts(parts, asm, info):
    b = part(parts, 'B')
    b['ops'] = [o for o in b['ops'] if not (o['kind'] == 'edge' and 'Minifix' in o['note'])]


def q_end_groove_half_depth(parts, asm, info):
    for code in ('E1', 'E2'):
        for o in part(parts, code)['ops']:
            if o['kind'] == 'groove':
                o['z'] = round(o['z'] / 2, 2)


# ------------------------------------------------------------------------------------------- DXF faults
def d_groove_full_depth(files):
    """Groove layer on the first groove sheet gets the contour (full board) depth."""
    for k in sorted(files):
        lays = _layers(files[k])
        groove = [l for l in lays if re.match(r'04_NOT_B[0-9P]+_Z[0-9P]+$', l)]
        kont = [l for l in lays if re.match(r'10_KONTUR_UTVENDIG_Z[0-9P]+$', l)]
        if groove and kont:
            zt = kont[0].rsplit('_Z', 1)[1]
            for g in groove:
                files[k] = _rename_layer(files[k], g, g.rsplit('_Z', 1)[0] + '_Z' + zt)
            return


def d_hdf_empty(files):
    for k in _sheet_with_label(files, 'SB')[:1]:
        head, ents, tail = _split(files[k])
        ents = [e for e in ents if _layer(e).startswith('00_')]
        files[k] = _build(head, ents, tail)


def d_pilot_through(files):
    k = _sheet_with_label(files, 'C')[0]
    cands = []
    for lay in _layers(files[k]):
        m = re.match(r'01_BOR_D([0-9P]+)_Z([0-9P]+)$', lay)
        if m and _num(m.group(2)) > 3:
            cands.append((_num(m.group(1)), lay, m.group(1)))
    _, lay, dtok = min(cands)
    files[k] = _rename_layer(files[k], lay, '02_HULL_D%s_GJENNOM' % dtok)


def d_groove_overrun(files):
    run = 40.0
    for k in sorted(files):
        head, ents, tail = _split(files[k])
        hit = False
        for i, e in enumerate(ents):
            if _kind(e) == 'POLYLINE' and _layer(e).startswith('04_NOT'):
                pts = _verts(e)
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
                if x1 - x0 >= y1 - y0:
                    x0, x1 = x0 - run, x1 + run
                else:
                    y0, y1 = y0 - run, y1 + run
                ents[i] = _set_verts(e, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
                hit = True
        if hit:
            files[k] = _build(head, ents, tail)


def d_double_compensation(files):
    off = _bit_d()
    k = _sheet_with_label(files, 'K')[0]
    head, ents, tail = _split(files[k])
    for i, e in enumerate(ents):
        if _kind(e) == 'POLYLINE' and _layer(e).startswith('10_KONTUR'):
            pts = _verts(e)
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            x0, x1, y0, y1 = min(xs) + off, max(xs) - off, min(ys) + off, max(ys) - off
            ents[i] = _set_verts(e, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    files[k] = _build(head, ents, tail)


def d_out_of_square(files):
    best = None
    for k in sorted(files):
        _, ents, _ = _split(files[k])
        for i, e in enumerate(ents):
            if _kind(e) == 'POLYLINE' and _layer(e).startswith('10_KONTUR'):
                pts = _verts(e)
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                a = (max(xs) - min(xs)) * (max(ys) - min(ys))
                if best is None or a > best[0]:
                    best = (a, k, i)
    _, k, i = best
    head, ents, tail = _split(files[k])
    pts = _verts(ents[i])
    pts[2] = (pts[2][0] - 5, pts[2][1])          # one corner pulled 5 mm in: parallelogram-ish, not a rectangle
    ents[i] = _set_verts(ents[i], pts)
    files[k] = _build(head, ents, tail)


def d_confirmat_countersink(files):
    for k in _sheet_with_label(files, 'S'):
        head, ents, tail = _split(files[k])
        lays = {l: n for l, n in _layers(files[k]).items() if l.startswith('02_HULL_D')}
        if not lays:
            continue
        lay = max(lays, key=lays.get)                # the most frequent through hole on a drawer sheet = confirmats
        for i, e in enumerate(ents):
            if _kind(e) == 'CIRCLE' and _layer(e) == lay:
                ents[i] = [(c, '%.3f' % (float(v) + 1.5) if c == '40' else v) for c, v in e]
        files[k] = _build(head, ents, tail)
        return


def d_labels_stripped(files):
    for k in _sheet_with_label(files, 'SH'):
        head, ents, tail = _split(files[k])
        files[k] = _build(head, [e for e in ents if _kind(e) != 'TEXT'], tail)


SRC_P = 'Designer input error (params.json), workshop experience'
SRC_G = 'Generator regression (kommode.py build())'
SRC_D = 'CAM/export/transfer error on the sheet DXF'

FAULTS = [
    # ---- params (8)
    Fault('h4_01', 'Dealer saw kerf entered as 0 mm (plater.sagsnitt)',
          'The panel saw removes ~4 mm per cut, but the offcut pieces are nested as if no material is lost: the second '
          'piece is drawn 4 mm larger than the real offcut, so parts nested at its far edge run off the board and are ruined.',
          p_kerf0, source=SRC_P + '; panel-saw kerf is always 3-4.5 mm'),
    Fault('h4_02', 'Front edge reveal (kant_topp_bunn) typed negative',
          'Front stack becomes taller than the carcass: the top drawer front runs up into the top overhang and cannot '
          'close, the bottom one hangs below the carcass - all 8 oak fronts recut.',
          params=p_reveal_neg, source=SRC_P + '; sign error when entering an overlay "overhang" instead of a reveal'),
    Fault('h4_03', 'Front-fixing screw holes in E1 copied from the confirmat layout (on the confirmat bore)',
          'The 4x30 front screws are drilled straight across the 5 mm confirmat pilot in the end grain of the front end: '
          'the confirmat and the screw collide, the end board splits and the front cannot be fixed.',
          params=p_frontscrew_on_confirmat, source=SRC_P + '; positions reused from the wrong hole table'),
    Fault('h4_04', 'Drawer side height lower than the slide (low-drawer option with a 46 mm slide)',
          'The slide body is taller than the drawer side: its screws run off the side, slide pilot holes break out '
          'of the edges and the drawer cannot be mounted.',
          params=p_box_lower_than_slide, source=SRC_P + '; wrong row from the slide catalogue'),
    Fault('h4_05', 'Rear plinth strip position entered for its back face (flush-intent), generator uses the front face',
          'Strip sticks out behind the carcass back so the chest cannot stand against the wall, and its screw holes '
          'break out of the bottom panel back edge.',
          params=p_rear_plinth_proud, source=SRC_P + '; reference-face confusion'),
    Fault('h4_06', 'Top front overhang typed 10x too large (e.g. 210 instead of 21)',
          'A deep unsupported top far in front of the front legs: leaning on it or a child climbing opened drawers '
          'tips the chest forward (tip-over hazard), and a big oak part is wasted.',
          params=p_overhang_x10, source=SRC_P + '; decimal slip; furniture tip-over injuries (EN 14749 / ASTM F2057)'),
    Fault('h4_07', 'Drawer bottom groove raised to half the box height (groove on the slide screw line)',
          'The groove runs exactly where the slide pilots go: slide screws end in the empty groove with no grip and the '
          'drawer side is weakened along the line carrying the load - drawers drop out under weight.',
          params=p_groove_mid_height, source=SRC_P + '; "hidden bottom" tweak without checking the hardware'),
    Fault('h4_08', 'Carcass depth typed as the slide length (430 -> 400)',
          'The slide needs more inside depth than its nominal length: drawers will not close fully against the back '
          'panel and the slide rear brackets clash with it - sides, bottom, top, middle wall all wrong depth.',
          params=p_depth_is_slide, source=SRC_P + '; slide minimum inside depth (Hettich KA spec)'),
    # ---- generator / parts (9)
    Fault('h4_09', 'Generator bug: spot-drill fallback lost - small-bit through holes sent as full-depth through cuts',
          'Holes smaller than the big bit (handle, slide pilots, plinth screws) are plunged through 18.8 mm with the '
          '1/8" bit whose flute is only 12.7 mm: shank rubs, bit overheats and snaps, burned holes.',
          parts=q_spot_lost, source=SRC_G + '; flute length vs. stock thickness, small-bit breakage'),
    Fault('h4_10', 'Generator bug: drawer bottom quantity = rows instead of rows x columns',
          'Only half the drawer bottoms are cut: four drawers cannot be assembled, a second HDF job (and maybe sheet) needed.',
          parts=q_sb_qty_rows, source=SRC_G),
    Fault('h4_11', 'Generator bug: middle wall quantity 0 (cols - 2)',
          'No middle wall is cut: the inner slides of both columns have nothing to mount on and the top/bottom holes '
          'for it lead nowhere - carcass cannot be assembled.',
          parts=q_no_middle_wall, source=SRC_G + '; off-by-one in a count'),
    Fault('h4_12', 'Generator bug: back drawer end E2 has no bottom groove',
          'The drawer bottom is sized to sit in grooves on all four sides; with no groove in the back end it hits E2 and '
          'the box cannot be closed - 8 back ends recut.',
          parts=q_e2_no_groove, source=SRC_G),
    Fault('h4_13', 'Generator bug: top cut to the inner width (between the sides) instead of the full width',
          'The top no longer covers the sides and its bolt/dowel holes for the sides fall off the part: wasted oak top.',
          parts=q_top_inner_width, source=SRC_G + '; length copied from the bottom panel formula'),
    Fault('h4_14', 'Generator bug: drawer fronts assigned to the white carcass board instead of the oak front board',
          'All 8 fronts are nested and cut from white melamine: wrong finish, sheets wasted, oak sheet half empty.',
          parts=q_fronts_white, source=SRC_G + '; wrong material role'),
    Fault('h4_15', 'Generator bug: top holes for the middle wall use the bottom panel coordinates (offset one board thickness)',
          'The top is measured from the outer edge but the bottom from inside the side: middle-wall bolt and dowel '
          'holes in the top miss the wall by ~19 mm, the wall stands crooked or cannot be joined.',
          parts=q_top_wall_holes_bottom_coords, source=SRC_G + '; wrong coordinate reference'),
    Fault('h4_16', 'Generator bug: bottom panel edge bores for the side Minifix bolts dropped',
          'Nothing for the cam bolts to enter: the bottom is held to the sides only by dowels and the carcass racks '
          'or falls apart when moved.',
          parts=q_bottom_no_side_bolts, source=SRC_G),
    Fault('h4_17', 'Generator bug: grooves in the drawer ends half as deep as the bottom is sized for',
          'Bottom is long enough for the full groove depth but E1/E2 grooves are shallow: the drawer box will not close '
          'by several mm, glue/confirmats pull the joints open.',
          parts=q_end_groove_half_depth, source=SRC_G),
    # ---- DXF (8)
    Fault('h4_18', 'DXF: groove layer on the first drawer sheet exported with the full board (contour) depth',
          'The bottom groove is cut right through the drawer sides/ends: every part on the sheet splits along the groove '
          'line and the whole sheet is scrap.',
          dxf=d_groove_full_depth, source=SRC_D + '; depth copied from the contour layer when the CAM layer map was built'),
    Fault('h4_19', 'DXF: drawer-bottom HDF sheet exported empty (only the sheet outline)',
          'The operator runs the job, nothing is cut: all 8 drawer bottoms missing at assembly time.',
          dxf=d_hdf_empty, source=SRC_D),
    Fault('h4_20', 'DXF: slide pilot holes on the oak sheet exported on a through-hole layer',
          'Blind slide pilots are drilled through the oak sides: rows of holes on the visible outside of the chest.',
          dxf=d_pilot_through, source=SRC_D + '; layer mapping error'),
    Fault('h4_21', 'DXF: bottom grooves overrun 40 mm past the part ends',
          'Grooves run out through the 10 mm gap into neighbouring parts: every neighbour gets a groove scar and is scrap.',
          dxf=d_groove_overrun, source=SRC_D + '; lead-in/lead-out added on the geometry instead of in CAM'),
    Fault('h4_22', 'DXF: tool compensation applied twice - contours on the front sheet offset inward by a bit diameter',
          'CAM offsets again for the bit, so every front comes out one bit diameter too small each way: gaps everywhere, '
          'handle holes off-centre - all fronts recut.',
          dxf=d_double_compensation, source=SRC_D + '; double cutter compensation (CAM + exporter)'),
    Fault('h4_23', 'DXF: one corner of the largest contour moved 5 mm (part out of square)',
          'Biggest part comes out as a trapezoid: carcass racks, gaps and joints do not close.',
          dxf=d_out_of_square, source=SRC_D + '; edited/snapped vertex in CAD'),
    Fault('h4_24', 'DXF: confirmat through-holes drawn with the Ø10 countersink circle on the Ø7 layer',
          'Geometry and layer disagree; CAM follows the circle and cuts Ø10 holes, the confirmat heads pull straight '
          'through the drawer sides.',
          dxf=d_confirmat_countersink, source=SRC_D),
    Fault('h4_25', 'DXF: part labels stripped from the drawer-box sheets',
          'Mirrored S/SH sides and E1/E2 ends are indistinguishable: wrong-handed sides go together, slide holes face '
          'inward, front-fixing holes end up at the back.',
          dxf=d_labels_stripped, source=SRC_D + '; text entities dropped by an export filter'),
]

VERSION = 4   # written blind by the red-team agent in loop round 4
