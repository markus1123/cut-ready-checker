"""Held-out red-team set h5: 25 fresh CNC flat-pack failure modes for the 8-drawer kommode.

Written blind (without the checker's rules). ~1/3 params (designer input), ~1/3 parts (generator bug),
~1/3 dxf (file/export bug). Every value is derived from the design or the files, never hard-coded sizes."""
import copy
import re

from fc.core import Fault
from faults.helpers import part


# ------------------------------------------------------------------------------------------------ dxf utils
def _lines(text):
    return text.split('\n')


def _ent_range(L):
    """(start, end) line indices of the ENTITIES section body (end = the '0' before its ENDSEC)."""
    s = next(i for i in range(0, len(L) - 1, 2) if L[i] == '2' and L[i + 1] == 'ENTITIES') + 2
    e = next(i for i in range(s, len(L) - 1, 2) if L[i] == '0' and L[i + 1] == 'ENDSEC')
    return s, e


def _blocks(L):
    """Top-level entities as [start, end) line ranges; a POLYLINE block runs through its SEQEND."""
    s, e = _ent_range(L)
    out, i = [], s
    while i < e:
        typ = L[i + 1]
        j = i + 2
        while j < e and L[j] != '0':
            j += 2
        if typ == 'POLYLINE':
            while j < e and not (L[j] == '0' and L[j + 1] == 'SEQEND'):
                j += 2
                while j < e and L[j] != '0':
                    j += 2
            j += 2
            while j < e and L[j] != '0':
                j += 2
        out.append((i, j, typ))
        i = j
    return out


def _layer(L, blk):
    i, j, _ = blk
    for k in range(i, j, 2):
        if L[k] == '8':
            return L[k + 1]
    return ''


def _verts(L, blk):
    """Line indices of the '10' code of every VERTEX in a POLYLINE block."""
    i, j, _ = blk
    out = []
    for k in range(i + 2, j, 2):
        if L[k] == '0' and L[k + 1] == 'VERTEX':
            m = k + 2
            while L[m] != '0':
                if L[m] == '10':
                    out.append(m)
                m += 2
    return out


def _bbox(L, blk):
    xs, ys = [], []
    for k in _verts(L, blk):
        xs.append(float(L[k + 1])); ys.append(float(L[k + 3]))
    return min(xs), min(ys), max(xs), max(ys)


def _contours(L):
    return [b for b in _blocks(L) if b[2] == 'POLYLINE' and _layer(L, b).startswith('10_KONTUR')]


def _largest(L):
    def area(b):
        x0, y0, x1, y1 = _bbox(L, b)
        return (x1 - x0) * (y1 - y0)
    return max(_contours(L), key=area)


def _file_with(files, needle):
    return [k for k in sorted(files) if needle in files[k]][0]


# ------------------------------------------------------------------------------------------------ params
def p_legs_front_from_back(P, S):
    dep = P['ytre']['dybde_korpus']
    P['korpus']['bein_senter'] = [[bx, dep - by] if by < dep / 2 else [bx, by] for bx, by in P['korpus']['bein_senter']]


def p_outer_thinner_board(P, S):
    valg = P['_valg']
    tk = valg['korpus']['tykkelse']
    cand = [m for m in P['_kat'].values() if m['tykkelse'] < tk and m['tykkelse'] >= 10
            and set(m['roller']) & {'ytre', 'korpus', 'skuff', 'front'}]
    m = min(cand, key=lambda m: (m['tykkelse'], m['id']))
    P['materialvalg']['ytre'] = m['id']
    valg['ytre'] = m


def p_min_bit_x10(P, S):
    P['plater']['min_bit'] = P['plater']['min_bit'] * 10


def p_plinth_inset_x10(P, S):
    P['korpus']['bunnlist_inn_fra_ende'] = P['korpus']['bunnlist_inn_fra_ende'] * 10


def p_groove_one_pass(P, S):
    P['maskintid']['omganger_not'] = 1


def p_confirmat_on_groove(P, S):
    D = P['skuff']
    gw = P['tykkelse_malt']['skuffebunn'] + D['not_klaring']
    D['konfirmat_y'] = [round(D['not_fra_underkant'] + gw / 2, 2)] + list(D['konfirmat_y'][1:])


def p_front_screws_on_front_height(P, S):
    F, Y = P['front'], P['ytre']
    fh = (Y['hoyde_side'] - 2 * F['kant_topp_bunn'] - (P['rader'] - 1) * F['fuge']) / P['rader']
    y0 = P['skuff']['front_skrue_y'][0]
    P['skuff']['front_skrue_y'] = [y0, round(fh - y0, 2)]


def p_cam_housing_hinge_cup(P, S):
    P['korpus']['minifix_hus_d'] = 35


# ------------------------------------------------------------------------------------------------ parts
def q_drawer_sides_short(parts, asm, info):
    ts = info['ts']
    for code in ('S', 'SH'):
        p = part(parts, code)
        L0 = p['L']
        p['L'] = round(L0 - 2 * ts, 2)
        for o in p['ops']:
            if 'x' in o and o['x'] > L0 / 2:
                o['x'] = round(o['x'] - 2 * ts, 2)
    for a in asm:
        if a['code'] in ('S', 'SH'):
            a['b'][4] = round(a['b'][4] - 2 * ts, 3)


def q_middle_wall_top_depth(parts, asm, info):
    A, D = part(parts, 'A'), part(parts, 'D')
    D['L'] = A['B']
    for a in asm:
        if a['code'] == 'D':
            a['b'][1] = -info['OV']; a['b'][4] = A['B']


def q_front_gets_fixing_holes(parts, asm, info):
    E1, K = part(parts, 'E1'), part(parts, 'K')
    dx = (K['L'] - E1['L']) / 2
    for o in E1['ops']:
        if o['kind'] == 'through':
            n = dict(o, x=round(o['x'] + dx, 2))
            n.pop('cnc', None)
            K['ops'].append(n)


def q_end_pilot_full_dia(parts, asm, info):
    d = [o['d'] for o in part(parts, 'S')['ops'] if o['kind'] == 'through' and 'onfirmat' in o['note']][0]
    for code in ('E1', 'E2'):
        for o in part(parts, code)['ops']:
            if o['kind'] == 'edge' and 'onfirmat' in o['note']:
                o['d'] = d


def q_end_pilot_as_face_hole(parts, asm, info):
    ts = info['ts']
    for code in ('E1', 'E2'):
        p = part(parts, code)
        ops = []
        for o in p['ops']:
            if o['kind'] == 'edge' and 'onfirmat' in o['note']:
                x = ts / 2 if 'venstre' in o['face'] else p['L'] - ts / 2
                ops.append(dict(face='F1', x=round(x, 2), y=o['pos'], d=o['d'], z='gjennom', note=o['note'], kind='through'))
            else:
                ops.append(o)
        p['ops'] = ops


def q_drawer_slide_pilots_blind_inside(parts, asm, info):
    z = [o['z'] for o in part(parts, 'C')['ops'] if o['kind'] == 'hole' and 'kinne-pilot' in o['note']][0]
    for code in ('S', 'SH'):
        for o in part(parts, code)['ops']:
            if 'kinne-pilot' in o['note'] and o['kind'] == 'through':
                o['kind'] = 'hole'; o['z'] = z; o['face'] = 'F1'
                o.pop('cnc', None)


def q_back_panel_includes_top(parts, asm, info):
    G = part(parts, 'G')
    G['B'] = round(info['HS'] + info['T'], 2)
    for a in asm:
        if a['code'] == 'G':
            a['b'][5] = G['B']


def q_groove_on_carcass_sides(parts, asm, info):
    g = [o for o in part(parts, 'S')['ops'] if o['kind'] == 'groove'][0]
    for code in ('C', 'CH'):
        part(parts, code)['ops'].append(copy.deepcopy(g))


def q_wall_housings_both_faces(parts, asm, info):
    D = part(parts, 'D')
    D['ops'] += [dict(o, face='F2') for o in D['ops'] if o['kind'] == 'hole' and o['note'].startswith('Minifix-hus')]


# ------------------------------------------------------------------------------------------------ dxf
def x_sheet_outline_as_contour(files):
    k = _file_with(files, '00_PLATE_REFERANSE')
    L = _lines(files[k])
    cl = re.search(r'10_KONTUR_UTVENDIG_Z[0-9P]+', files[k]).group(0)
    for b in _blocks(L):
        if _layer(L, b) == '00_PLATE_REFERANSE':
            for i in range(b[0], b[1], 2):
                if L[i] == '8':
                    L[i + 1] = cl
    files[k] = '\n'.join(L)


def x_groove_width_depth_swapped(files):
    k = _file_with(files, '04_NOT_B')
    files[k] = re.sub(r'04_NOT_B([0-9P]+)_Z([0-9P]+)', r'04_NOT_B\2_Z\1', files[k])


def x_contour_bulge(files):
    k = _file_with(files, '10_KONTUR')
    L = _lines(files[k])
    ins = []
    for b in _contours(L):
        for v in _verts(L, b):
            ins.append(v + 6)          # after 10/x, 20/y, 30/z
    for i in sorted(ins, reverse=True):
        assert L[i - 2] == '30'
        L[i:i] = ['42', '0.02']
    files[k] = '\n'.join(L)


def x_stray_origin_vertex(files):
    k = sorted(f for f in files if '10_KONTUR' in files[f])[1]
    L = _lines(files[k])
    b = _largest(L)
    v = _verts(L, b)[1]
    lay = _layer(L, b)
    L[v + 6:v + 6] = ['0', 'VERTEX', '8', lay, '10', '0.000', '20', '0.000', '30', '0']
    files[k] = '\n'.join(L)


def x_two_sheets_merged(files):
    groups = {}
    for f in sorted(files):
        m = re.match(r'^[A-Za-z]+\d+_(.+)_\d+x\d+\.dxf$', f)
        if m:
            groups.setdefault(m.group(1), []).append(f)
    a, b = [g for g in groups.values() if len(g) >= 2][0][:2]
    LB = _lines(files[b])
    extra = []
    for blk in _blocks(LB):
        if _layer(LB, blk) != '00_PLATE_REFERANSE':
            extra += LB[blk[0]:blk[1]]
    LA = _lines(files[a])
    _, e = _ent_range(LA)
    LA[e:e] = extra
    files[a] = '\n'.join(LA)


def x_grooves_stop_short(files, stop=25.0):
    k = _file_with(files, '04_NOT_B')
    L = _lines(files[k])
    for b in _blocks(L):
        if b[2] != 'POLYLINE' or not _layer(L, b).startswith('04_NOT'):
            continue
        x0, y0, x1, y1 = _bbox(L, b)
        along_x = (x1 - x0) >= (y1 - y0)
        for v in _verts(L, b):
            i = v if along_x else v + 2
            lo, hi = (x0, x1) if along_x else (y0, y1)
            val = float(L[i + 1])
            L[i + 1] = '%.3f' % (val + stop if abs(val - lo) < 1e-6 else val - stop if abs(val - hi) < 1e-6 else val)
    files[k] = '\n'.join(L)


def x_through_as_blind(files):
    k = _file_with(files, '02_HULL_D')
    lay = sorted(set(re.findall(r'02_HULL_D([0-9P]+)_GJENNOM', files[k])), key=lambda s: -float(s.replace('P', '.')))[0]
    files[k] = files[k].replace('02_HULL_D%s_GJENNOM' % lay, '01_BOR_D%s_Z5' % lay)


def x_contour_elevation(files):
    k = sorted(f for f in files if '10_KONTUR' in files[f])[-1]
    L = _lines(files[k])
    for b in _contours(L):
        z = re.search(r'_Z([0-9P]+)', _layer(L, b)).group(1).replace('P', '.')
        for i in range(b[0], b[1], 2):
            if L[i] == '30':
                L[i + 1] = '-' + z
    files[k] = '\n'.join(L)


# ------------------------------------------------------------------------------------------------ the set
FAULTS = [
    # --- params (designer input) ---
    Fault('h5_01', 'Front leg positions measured from the back edge: all four legs in the rear half',
          'bein_senter y for the front legs entered from the back. All legs end up near the back, the whole drawer '
          'load is cantilevered in front of the support line - the kommode tips forward when a loaded drawer is opened.',
          params=p_legs_front_from_back,
          source='CPSC / ASTM F2057 furniture tip-over: support base vs. drawer extension; leg placement drawings'),
    Fault('h5_02', 'Top + sides switched to a thinner (16 mm) board in materialvalg while carcass stays 19 mm',
          'The outer parts are still sized, drilled and contoured for the 18.8 mm carcass thickness, but the sheet '
          'is 16 mm: contours plunge ~3 mm into the spoilboard, Minifix bolts/housings no longer meet, carcass is out of square.',
          params=p_outer_thinner_board,
          source='Workshop: substituting a cheaper/thinner board at order time without re-running the joint layout'),
    Fault('h5_03', 'Dealer offcut minimum typed 1500 instead of 150 mm (plater.min_bit)',
          'Every saw-split piece under 1.5 m is dropped, so the 846 mm strip of each 2800x2070 sheet is thrown away '
          'and the nest needs extra whole sheets - wasted oak and an order that does not match the cut plan.',
          params=p_min_bit_x10,
          source='Panel-saw splitting at the dealer; extra zero typed in a parameter file'),
    Fault('h5_04', 'Plinth inset from the ends typed 810 instead of 81 mm (strip length negative)',
          'bunnlist_inn_fra_ende x10: the plinth length LB - 2*inset becomes negative/impossible and the screw holes '
          'in the bottom land outside any strip - nothing can be cut or assembled under the bottom.',
          params=p_plinth_inset_x10,
          source='Extra digit in a parametric input; plinth sizing'),
    Fault('h5_05', 'Bottom groove programmed in a single pass (maskintid.omganger_not = 1)',
          'The full 8 mm deep groove is cut in one pass with the 1/8" bit (groove < 6.35 mm) - 2.5x the bit diameter '
          'in one go snaps the small bit and burns the melamine.',
          params=p_groove_one_pass,
          source='Router-bit makers: max depth of cut per pass ~1x diameter for 1/8" bits in particle board'),
    Fault('h5_06', 'Lower confirmat height set on the bottom-groove line',
          'konfirmat_y[0] placed at the centre of the bottom groove: the 7 mm confirmat hole goes through the groove, '
          'the screw lands in the HDF slot, the joint has nothing to bite into and the groove edge blows out.',
          params=p_confirmat_on_groove,
          source='Drawer box joinery: fasteners must clear the bottom groove'),
    Fault('h5_07', 'Front-fixing screw heights laid out on the 160 mm front instead of the 120 mm drawer end',
          'front_skrue_y taken from the front height: the upper fixing holes fall at or beyond the top edge of the '
          'E1 drawer end - holes break out of the part, front cannot be screwed on.',
          params=p_front_screws_on_front_height,
          source='Measuring from the wrong drawing (front vs. box end)'),
    Fault('h5_08', 'Minifix housing diameter set to 35 mm (hinge-cup Forstner size)',
          'minifix_hus_d 35 instead of 15: the pocket is far wider than the cam, the 24 mm housing distance puts the '
          'pocket over the board edge - edges blow out and the cam has no wall to pull against.',
          params=p_cam_housing_hinge_cup,
          source='Hettich/Häfele: Minifix 15 housing Ø15; Ø35 is the concealed-hinge cup bit'),

    # --- parts (generator bug) ---
    Fault('h5_09', 'Generator bug: drawer sides shortened by two end-board thicknesses',
          'S/SH cut to Ls - 2*ts as if the ends were butted outside the sides: the box is 37.6 mm shorter than the '
          'slide, the drawer ends no longer reach the bottom grooves of the sides and the slide overhangs the box.',
          parts=q_drawer_sides_short,
          source='Classic butt-joint formula error (end thickness subtracted on the wrong part)'),
    Fault('h5_10', 'Generator bug: middle wall cut to the top depth (front overhang + back panel included)',
          'D length taken from the top (OV + DEP + back): the wall sticks out in front of the carcass and hits the '
          'drawer fronts; at the back it collides with the back panel - fronts cannot close.',
          parts=q_middle_wall_top_depth,
          source='Copying the wrong reference dimension between parts'),
    Fault('h5_11', 'Generator bug: drawer-end front-fixing holes also drilled through the oak fronts',
          'The E1 Ø8 through-hole pattern is appended to the K fronts: four visible holes through every one of the '
          '8 oak fronts - all fronts scrapped.',
          parts=q_front_gets_fixing_holes,
          source='Shared op list reused between mating parts'),
    Fault('h5_12', 'Generator bug: confirmat end-grain pilots in E1/E2 at full screw diameter (Ø7 instead of Ø5)',
          'The pilot in the end grain equals the confirmat shank: the thread has nothing to cut into chipboard end grain, '
          'screws spin out and the drawer box falls apart.',
          parts=q_end_pilot_full_dia,
          source='Confirmat 7x50: clearance Ø7 in the face, pilot Ø5 in the end grain (Häfele)'),
    Fault('h5_13', 'Generator bug: confirmat end-grain pilots of E1/E2 emitted as through-holes in the face',
          'Edge ops converted to CNC through-holes at the part ends: holes through the face of every drawer end, '
          'small bit plunged through 18.8 mm, and the end grain has no pilot for the screw.',
          parts=q_end_pilot_as_face_hole,
          source='Edge vs. face op confusion in a CAM post'),
    Fault('h5_14', 'Generator bug: drawer-side slide pilots cut 10 mm blind from the inner face',
          'Slide screws enter from the outside of S/SH, but the pilots are blind holes from the inside face: the outer '
          'face has no hole and the blind hole breaks the 2.8 mm skin - slides cannot be fixed accurately.',
          parts=q_drawer_slide_pilots_blind_inside,
          source='Side-mount slide installation (screw face vs. machined face)'),
    Fault('h5_15', 'Generator bug: back panel height includes the top thickness',
          'G cut HS + T tall: it stands 18.8 mm proud of the sides into the zone the top covers - the top cannot sit '
          'down on the carcass, joints gape.',
          parts=q_back_panel_includes_top,
          source='Back panel captured under the top vs. on top of the sides'),
    Fault('h5_16', 'Generator bug: drawer-bottom groove also cut into the carcass sides',
          'The groove op is appended to C and CH: a 6.4 mm slot runs the full depth of both oak sides, visible at the '
          'front edge and through the Minifix bolt holes - both sides scrapped.',
          parts=q_groove_on_carcass_sides,
          source='Shared op dict leaking between part builders'),
    Fault('h5_17', 'Generator bug: middle-wall Minifix housings drilled on both faces',
          'Housings 14 mm deep from F1 and again from F2 at the same spots in an 18.8 mm wall: they meet, leaving '
          'holes through the wall and no material for the cams.',
          parts=q_wall_housings_both_faces,
          source='Double-sided part with mirrored op list applied twice'),

    # --- dxf (file / export bug) ---
    Fault('h5_18', 'DXF: sheet reference outline exported on the outer-contour layer',
          'The 00_PLATE_REFERANSE rectangle lands on the contour layer: CAM profiles the sheet border at full depth, '
          'running the bit into clamps/screws at the sheet edge - broken bit, unsafe.',
          dxf=x_sheet_outline_as_contour,
          source='Layer mapping errors in CAM import'),
    Fault('h5_19', 'DXF: groove layer width and depth swapped (B6P4_Z8 -> B8_Z6P4)',
          'The groove is cut 8 mm wide and 6.4 mm deep: the HDF bottom rattles in the slot and is sized for a deeper '
          'groove, so it does not fit between the drawer parts.',
          dxf=x_groove_width_depth_swapped,
          source='Layer-name template fields swapped in the exporter'),
    Fault('h5_20', 'DXF: bulge values on contour vertices (straight edges exported as arcs)',
          'Group 42 bulge set on every vertex of one sheet: the CAM cuts each edge as an arc - parts bow in/out by '
          'several mm over their length and nothing fits.',
          dxf=x_contour_bulge,
          source='Polyline bulge left over from a fillet/offset operation'),
    Fault('h5_21', 'DXF: stray vertex at the origin inserted into the largest contour',
          'An uninitialised (0,0) vertex in a contour: the toolpath jumps diagonally across the sheet at full depth, '
          'cutting through the neighbouring parts.',
          dxf=x_stray_origin_vertex,
          source='Exporter emits default-initialised vertex'),
    Fault('h5_22', 'DXF: two sheets of the same board written into one file',
          'The parts of the second sheet are appended to the first: overlapping contours and holes on one sheet - '
          'the cut destroys both sets of parts.',
          dxf=x_two_sheets_merged,
          source='Export loop not resetting the entity buffer between sheets'),
    Fault('h5_23', 'DXF: bottom grooves stop 25 mm short of the part ends',
          'Grooves no longer run out at the ends: the HDF bottom cannot reach under the end boards, the box cannot be '
          'closed, and stopped grooves leave rounded ends.',
          dxf=x_grooves_stop_short,
          source='Lead-in/lead-out trimmed into the geometry'),
    Fault('h5_24', 'DXF: largest through-hole layer exported as a 5 mm blind drill',
          'Through holes (confirmat/front-fixing) on one sheet become 5 mm deep blind holes: screws cannot pass, '
          'every hole must be re-drilled by hand and will wander.',
          dxf=x_through_as_blind,
          source='CAM layer template mapping GJENNOM to a fixed drill depth'),
    Fault('h5_25', 'DXF: contour vertices on one sheet exported at Z = -board thickness',
          'Elevation added to the vertices: CAM that uses geometry Z adds it to the layer depth and cuts twice the '
          'board thickness deep - into the spoilboard/bed, bit overloaded.',
          dxf=x_contour_elevation,
          source='3D-polyline elevation leaking into a 2D export'),
]

VERSION = 5   # written blind by the red-team agent in loop round 5
