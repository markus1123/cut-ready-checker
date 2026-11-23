"""Held-out set 3: blind red-team faults (y01-y25). Written without looking at the checker."""
import re
from fc.core import Fault


# ------------------------------------------------------------------------------------------- helpers
def _codes(parts, *codes):
    return [p for p in parts if p['code'] in codes]


def _blocks(text):
    """Split DXF text into (head_lines, [entity line-lists], tail_lines) for the ENTITIES section.
    Each entity block starts with '0' / TYPE and includes its VERTEX/SEQEND lines for polylines."""
    lines = text.split('\n')
    start = None
    for i in range(0, len(lines) - 1, 2):
        if lines[i] == '2' and lines[i + 1] == 'ENTITIES':
            start = i + 2
            break
    if start is None:
        raise ValueError('no ENTITIES')
    end = None
    for i in range(start, len(lines) - 1, 2):
        if lines[i] == '0' and lines[i + 1] == 'ENDSEC':
            end = i
            break
    head, body, tail = lines[:start], lines[start:end], lines[end:]
    ents, cur = [], None
    for i in range(0, len(body) - 1, 2):
        c, v = body[i], body[i + 1]
        if c == '0' and v in ('POLYLINE', 'CIRCLE', 'TEXT', 'LINE', 'ARC', 'LWPOLYLINE'):
            cur = [c, v]
            ents.append(cur)
        else:
            cur += [c, v]
    return head, ents, tail


def _join(head, ents, tail):
    out = list(head)
    for e in ents:
        out += e
    return '\n'.join(out + tail)


def _layer(e):
    for i in range(2, len(e) - 1, 2):
        if e[i] == '8':
            return e[i + 1]
    return ''


def _xy(e):
    """All (index_of_x, index_of_y) value positions in an entity block."""
    out, ix = [], None
    for i in range(2, len(e) - 1, 2):
        if e[i] == '10':
            ix = i + 1
        elif e[i] == '20' and ix is not None:
            out.append((ix, i + 1))
            ix = None
    return out


def _poly_pts(e):
    """Vertex coordinates of a POLYLINE block (skips the polyline's own dummy 10/20 header point)."""
    pts, in_v = [], False
    ix = None
    for i in range(2, len(e) - 1, 2):
        if e[i] == '0' and e[i + 1] == 'VERTEX':
            in_v = True
        if not in_v:
            continue
        if e[i] == '10':
            ix = i + 1
        elif e[i] == '20' and ix is not None:
            pts.append((ix, i + 1)); ix = None
    return pts


def _bbox(e):
    pts = _poly_pts(e)
    xs = [float(e[a]) for a, _ in pts]; ys = [float(e[b]) for _, b in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _contours(ents):
    return [e for e in ents if e[1] == 'POLYLINE' and re.match(r'^10_KONTUR', _layer(e))]


def _sheet_with(files, layer_re):
    """Name of the first sheet (sorted) whose entities use a layer matching layer_re."""
    for k in sorted(files):
        _, ents, _ = _blocks(files[k])
        if any(re.match(layer_re, _layer(e)) for e in ents):
            return k
    raise ValueError('no sheet with layer ' + layer_re)


def _inside(e, bb):
    for ix, iy in _xy(e):
        x, y = float(e[ix]), float(e[iy])
        if not (bb[0] < x < bb[2] and bb[1] < y < bb[3]):
            return False
    return True


# ------------------------------------------------------------------------------------- params faults
def p_handle_hole_3(P, S):
    P['front']['handtak_hull_d'] = 3


def p_minifix_bolt_8(P, S):
    P['korpus']['minifix_bolt_d'] = 8


def p_pilot_depth_18(P, S):
    S['pilot_dybde'] = 18


def p_bed_2500(P, S):
    P['verksted']['plate_maks'] = [2500, 1250]


def p_leg_off_bottom(P, S):
    P['korpus']['bein_senter'] = [[x, y + 100 if y > 200 else y] for x, y in P['korpus']['bein_senter']]


def p_height_typo(P, S):
    P['ytre']['hoyde_side'] = P['ytre']['hoyde_side'] + 1000


def p_fix_hole_14(P, S):
    P['front']['justerbar_feste'] = True
    P['front']['festehull_d_justerbar'] = 14


def p_minifix_near_edge(P, S):
    P['korpus']['minifix_inn_fra_kant'] = 8


def p_hdf_59(P, S):
    P['tykkelse_malt']['skuffebunn'] = round(P['tykkelse_malt']['skuffebunn'] * 10, 1)


# -------------------------------------------------------------------------------------- parts faults
def g_back_panel_depth(parts, asm, info):
    for p in _codes(parts, 'G'):
        p['B'] = info['DEP']


def g_sides_carcass_depth(parts, asm, info):
    for p in _codes(parts, 'S', 'SH'):
        p['L'] = info['DEP']


def g_confirmat_on_face(parts, asm, info):
    ts = info['ts']
    for p in _codes(parts, 'S', 'SH'):
        for o in p['ops']:
            if 'onfirmat' in o['note'] and 'x' in o:
                o['x'] = round(o['x'] + ts / 2 if o['x'] < p['L'] / 2 else o['x'] - ts / 2, 2)


def g_one_handle_hole(parts, asm, info):
    for p in _codes(parts, 'K'):
        hh = [o for o in p['ops'] if 'åndtak' in o['note']]
        p['ops'].remove(hh[-1])


def g_bottom_swapped(parts, asm, info):
    for p in _codes(parts, 'SB'):
        p['L'], p['B'] = p['B'], p['L']


def g_front_screws_on_back(parts, asm, info):
    e1 = _codes(parts, 'E1')[0]; e2 = _codes(parts, 'E2')[0]
    mv = [o for o in e1['ops'] if o['kind'] == 'through' and 'front' in o['note'].lower()]
    assert mv
    for o in mv:
        e1['ops'].remove(o)
        e2['ops'].append(o)


def g_housing_wrong_end(parts, asm, info):
    hit = 0
    for p in _codes(parts, 'C', 'CH'):
        for o in p['ops']:
            if 'hus' in o['note'].lower() and 'topp' in o['note'].lower():
                o['y'] = round(p['B'] - o['y'], 2); hit += 1
    assert hit


def g_groove_from_side_thk(parts, asm, info):
    for p in _codes(parts, 'S', 'SH', 'E1', 'E2'):
        for o in p['ops']:
            if o['kind'] == 'groove':
                o['y2'] = round(o['y1'] + info['ts'] + 0.5, 2)


# ---------------------------------------------------------------------------------------- dxf faults
def d_origin_centre(files):
    k = _sheet_with(files, r'^10_KONTUR')
    m = re.search(r'_(\d+)x(\d+)\.dxf$', k)
    W, H = float(m.group(1)), float(m.group(2))
    head, ents, tail = _blocks(files[k])
    for e in ents:
        for ix, iy in _xy(e):
            e[ix] = '%.3f' % (float(e[ix]) - W / 2)
            e[iy] = '%.3f' % (float(e[iy]) - H / 2)
    files[k] = _join(head, ents, tail)


def d_holes_not_translated(files):
    k = _sheet_with(files, r'^0[123]_')
    head, ents, tail = _blocks(files[k])
    for c in _contours(ents):
        bb = _bbox(c)
        circ = [e for e in ents if e[1] == 'CIRCLE' and _inside(e, bb)]
        if circ and (bb[0] > 50 or bb[1] > 50):
            for e in circ:
                for ix, iy in _xy(e):
                    e[ix] = '%.3f' % (float(e[ix]) - bb[0])
                    e[iy] = '%.3f' % (float(e[iy]) - bb[1])
            files[k] = _join(head, ents, tail)
            return
    raise ValueError('no part with holes away from origin')


def d_pocket_shift(files):
    k = _sheet_with(files, r'^03_LOMME')
    head, ents, tail = _blocks(files[k])
    for e in ents:
        if e[1] == 'CIRCLE' and _layer(e).startswith('03_LOMME'):
            for ix, iy in _xy(e):
                e[ix] = '%.3f' % (float(e[ix]) + 8)
                e[iy] = '%.3f' % (float(e[iy]) + 8)
    files[k] = _join(head, ents, tail)


def d_groove_as_contour(files):
    hit = False
    for k in sorted(files):
        head, ents, tail = _blocks(files[k])
        t = None
        for e in ents:
            m = re.match(r'^10_KONTUR_UTVENDIG_(Z[0-9P]+)', _layer(e))
            if m:
                t = m.group(1)
        changed = False
        for e in ents:
            if re.match(r'^04_NOT', _layer(e)) and t:
                for i in range(2, len(e) - 1, 2):
                    if e[i] == '8':
                        e[i + 1] = '10_KONTUR_UTVENDIG_' + t
                changed = hit = True
        if changed:
            files[k] = _join(head, ents, tail)
            return
    assert hit, 'no groove layer'


def d_truncated(files):
    k = _sheet_with(files, r'^04_NOT')
    head, ents, tail = _blocks(files[k])
    keep = ents[:max(1, int(len(ents) * 0.55))]
    files[k] = '\n'.join(head + [x for e in keep for x in e])


def d_depth_decimal_lost(files):
    k = _sheet_with(files, r'^10_KONTUR_UTVENDIG_Z\d+P\d+')
    files[k] = re.sub(r'(10_KONTUR_UTVENDIG_Z)(\d+)P(\d+)', r'\1\2\3', files[k])


def d_contour_rotated(files):
    for k in sorted(files):
        head, ents, tail = _blocks(files[k])
        for c in _contours(ents):
            x0, y0, x1, y1 = _bbox(c)
            w, h = x1 - x0, y1 - y0
            bb = (x0, y0, x1, y1)
            if abs(w - h) > 100 and any(e[1] == 'CIRCLE' and _inside(e, bb) for e in ents):
                for ix, iy in _poly_pts(c):
                    x, y = float(c[ix]) - x0, float(c[iy]) - y0
                    c[ix] = '%.3f' % (x0 + y)
                    c[iy] = '%.3f' % (y0 + x)
                files[k] = _join(head, ents, tail)
                return
    raise ValueError('no non-square contour with holes')


def d_pilot_layer_frozen(files):
    k = _sheet_with(files, r'^0[12]_\w*D3P1')
    head, ents, tail = _blocks(files[k])
    ents = [e for e in ents if not (e[1] == 'CIRCLE' and re.match(r'^0[12]_\w*D3P1', _layer(e)))]
    files[k] = _join(head, ents, tail)


FAULTS = [
    # --- params (designer / input errors)
    Fault('y01', 'Handle hole diameter typed as 3 mm for M4 handle bolts',
          'The M4 handle bolts do not pass through the Ø3 holes in the fronts; drilling them out by hand on the finished oak fronts chips the decor and the handles end up crooked.',
          params=p_handle_hole_3, source='Hardware fit: thread size confused with tap-drill size'),
    Fault('y02', 'Minifix bolt pilot holes set to Ø8 (dowel size) instead of Ø5',
          'The screw-in Minifix bolts have nothing to bite into in an Ø8 hole, so the carcass joints to the top, bottom and middle wall cannot be tightened; every joint hole is wrong.',
          params=p_minifix_bolt_8, source='Joinery: dowel diameter copied into the Minifix bolt field'),
    Fault('y03', 'Slide pilot depth set to 18 mm in 18.8 mm sides',
          'Slide pilot holes go (almost) through the side panels and blow out on the visible oak outside face of the carcass at every slide screw.',
          params=p_pilot_depth_18, source='Tooling: blind-hole depth entered as board thickness'),
    Fault('y04', 'Machine bed entered as 2500x1250 (sheet-ish size) instead of the router\'s 2440x1220',
          'The dealer saws pieces bigger than the ShopBot bed and the nest uses the extra 60/30 mm: parts at the far end cannot be reached or clamped, the job overruns the machine limits.',
          params=p_bed_2500, source='Nesting/sheet: machine envelope taken from a quote instead of the workshop'),
    Fault('y05', 'Rear leg positions 100 mm deeper than the carcass',
          'The rear legs are marked outside the bottom panel: they hang off the back, cannot be screwed to the bottom and the chest rocks/tips backwards.',
          params=p_leg_off_bottom, source='Assembly/safety: leg y measured from the top front edge instead of the carcass front'),
    Fault('y06', 'Side height typed 1653 instead of 653',
          'A 1.65 m tall, 43 cm deep chest of drawers with only four drawers: sides and back are cut far too long and the finished piece is a tip-over hazard.',
          params=p_height_typo, source='Geometry: extra digit in an outer dimension'),
    Fault('y07', 'Adjustable front-fixing holes in the drawer front ends set to Ø14',
          'The 4x30 screws and their washers pull straight through the Ø14 holes, so the fronts cannot be fastened to the drawer boxes.',
          params=p_fix_hole_14, source='Hardware fit: washer diameter typed as the slot/hole size'),
    Fault('y08', 'Minifix/joint positions set 8 mm from the front and back edges',
          'Ø15 cam housings and bolt holes break out of the front edge of the sides/middle wall, the edge bores split the chipboard and the joints have no strength.',
          params=p_minifix_near_edge, source='Joinery: edge distance from a 16 mm system drawing misread'),
    Fault('y09', 'Drawer-bottom HDF thickness typed 59 instead of 5.9',
          'The bottom groove becomes ~60 mm wide on 120 mm drawer parts: it eats half the drawer side, crosses the confirmat holes and the box falls apart.',
          params=p_hdf_59, source='Materials: decimal point lost when entering a measured thickness'),
    # --- parts (generator bugs)
    Fault('y10', 'Generator bug: back panel height taken from carcass depth (430) instead of side height',
          'The back panel is cut 430 mm high on a 653 mm carcass: the back is open, the carcass is not squared and the panel sheet is wasted.',
          parts=g_back_panel_depth, source='Generator: wrong variable for one dimension'),
    Fault('y11', 'Generator bug: drawer sides cut to carcass depth instead of slide length',
          'Drawer sides become 430 mm while ends, bottoms and slides are for 400: the bottom no longer reaches the back groove, the box hits the back panel and drawers do not close.',
          parts=g_sides_carcass_depth, source='Drawer mechanics: slide length vs carcass depth confusion'),
    Fault('y12', 'Generator bug: confirmat holes in drawer sides offset to the inner face of the end boards',
          'The 7 mm confirmat holes sit on the joint line instead of the centre of the 18.8 mm end: screws split out of the end grain and the drawer boxes cannot be assembled.',
          parts=g_confirmat_on_face, source='Joinery: hole at board thickness instead of half thickness'),
    Fault('y13', 'Generator bug: only one handle hole on every drawer front',
          'Two-bolt bar handles cannot be fitted; drilling the second hole by hand on finished oak fronts gives misaligned handles across all eight drawers.',
          parts=g_one_handle_hole, source='Hardware: list-index bug drops the last op'),
    Fault('y14', 'Generator bug: drawer bottom length and width swapped',
          'Bottoms are cut 377 x 725 instead of 725 x 377: they cannot go into the drawer box grooves at all, all eight bottoms are scrap.',
          parts=g_bottom_swapped, source='Geometry: L/B transposed for one part'),
    Fault('y15', 'Generator bug: front-fixing screw holes drilled in the back end (E2) instead of the front end (E1)',
          'There is no way to screw the fronts to the drawer boxes from inside; the holes in the back ends are useless.',
          parts=g_front_screws_on_back, source='Assembly: ops attached to the wrong part'),
    Fault('y16', 'Generator bug: side Minifix housings for the top drawn at the bottom end of the sides',
          'The top-edge bolts in the sides have no cam housing to engage, the top cannot be locked down and there are stray Ø15 pockets near the bottom joint.',
          parts=g_housing_wrong_end, source='Joinery: y measured from the wrong reference edge'),
    Fault('y17', 'Generator bug: bottom groove width from drawer-side thickness instead of HDF thickness',
          'Grooves are ~19 mm wide for a 6 mm bottom: the bottom rattles, the groove runs into the confirmat holes and the lower edge of the drawer parts breaks off.',
          parts=g_groove_from_side_thk, source='Drawer mechanics: wrong thickness variable for a groove'),
    # --- dxf (file / export bugs)
    Fault('y18', 'DXF: one sheet exported with its origin at the sheet centre',
          'All coordinates are shifted by half a sheet into negative X/Y: with zero at the sheet corner the router runs off the sheet into clamps/limits and cuts the parts in the wrong places.',
          dxf=d_origin_centre, source='File format: drawing origin vs machine zero'),
    Fault('y19', 'DXF: holes of one part left in part-local coordinates (not moved with the part)',
          'The holes of one part are drilled near the sheet origin, through a neighbouring part or the margin, while the part itself is cut without its holes.',
          dxf=d_holes_not_translated, source='Export: block explode / transform not applied to child entities'),
    Fault('y20', 'DXF: Minifix housing pockets shifted 8 mm on one sheet',
          'The cam housings no longer line up with the edge-bored bolts, so the cams cannot catch the bolts and the carcass joints do not close.',
          dxf=d_pocket_shift, source='Export: pocket layer offset (tool-compensation / layer offset applied twice)'),
    Fault('y21', 'DXF: bottom-groove rectangles exported on the outer-contour layer',
          'The CAM profiles every groove full depth: all drawer sides and ends are sliced into strips.',
          dxf=d_groove_as_contour, source='Layers: wrong layer mapping in the export'),
    Fault('y22', 'DXF: sheet file truncated during transfer (last ~45% of entities and EOF missing)',
          'Depending on the CAM, the import fails or silently loads only half of the parts/holes; the sheet is cut incomplete and the missing parts are discovered at assembly.',
          dxf=d_truncated, source='File transfer: USB stick pulled / upload interrupted'),
    Fault('y23', 'DXF: decimal marker lost in contour-layer depth (Z18P8 -> Z188)',
          'CAM layer mapping reads a 188 mm cut depth: the bit plunges through the sheet and spoilboard into the table, breaking the bit.',
          dxf=d_depth_decimal_lost, source='File format: layer-name encoding of depth corrupted'),
    Fault('y24', 'DXF: one part\'s contour exported rotated 90 deg while its holes are not',
          'The part is cut to the wrong outline: its holes and grooves fall outside it and it cuts across its neighbours on the sheet.',
          dxf=d_contour_rotated, source='Export: rotation applied to the outline but not to the machining'),
    Fault('y25', 'DXF: slide pilot-hole layer frozen at export (all Ø3.175 pilots missing on one sheet)',
          'The slide mounting holes are not drilled: slides must be positioned by hand, drawers end up crooked and the fronts do not line up.',
          dxf=d_pilot_layer_frozen, source='Layers: frozen/off layer not exported'),
]

VERSION = 3   # third blind held-out set, written after v2 was retired
