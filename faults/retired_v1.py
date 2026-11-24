"""RETIRED held-out set v1 (red team). Its misses were studied on 2026-11-22, so it now counts as practice.. Written without looking at fc/rules or faults/train.py.

Each fault is a real way a flat-pack CNC job goes wrong. ~1/3 designer/input errors (params), ~1/3 generator
bugs (parts), ~1/3 export/nesting/file faults (dxf)."""
import re
from fc.core import Fault


# ------------------------------------------------------------------------------------------- helpers
def _p(parts, code):
    return [p for p in parts if p['code'] == code][0]


def _sheet(files, needle):
    return [k for k in sorted(files) if needle in k][0]


def _split(text):
    """-> (head lines incl. 'ENTITIES', [entity blocks as line lists], tail lines from ENDSEC)."""
    L = text.split('\n')
    i = next(k for k in range(0, len(L) - 1, 2) if L[k] == '2' and L[k + 1] == 'ENTITIES') + 2
    head, blocks, cur, j = L[:i], [], None, i
    while j < len(L) - 1:
        c, v = L[j], L[j + 1]
        if c == '0' and v in ('POLYLINE', 'CIRCLE', 'TEXT', 'ENDSEC'):
            if v == 'ENDSEC':
                break
            cur = [c, v]; blocks.append(cur)
        else:
            cur += [c, v]
        j += 2
    return head, blocks, L[j:]


def _join(head, blocks, tail):
    out = list(head)
    for b in blocks:
        out += b
    return '\n'.join(out + tail)


def _layer(b):
    return b[b.index('8') + 1] if '8' in b[::2] else ''


def _xy(b):
    """All (x, y) points of a block (vertices for polylines, centre/insert for circle/text)."""
    pts, x = [], None
    for k in range(0, len(b) - 1, 2):
        if b[k] == '10':
            x = float(b[k + 1])
        elif b[k] == '20' and x is not None:
            pts.append((x, float(b[k + 1]))); x = None
    if b[1] == 'POLYLINE':
        pts = pts[1:]  # first 10/20 is the polyline's dummy origin
    return pts


def _map(b, fx=None, fy=None, fr=None):
    b = list(b)
    for k in range(0, len(b) - 1, 2):
        if b[k] == '10' and fx: b[k + 1] = '%.3f' % fx(float(b[k + 1]))
        if b[k] == '20' and fy: b[k + 1] = '%.3f' % fy(float(b[k + 1]))
        if b[k] == '40' and fr: b[k + 1] = '%.3f' % fr(float(b[k + 1]))
    if b[1] == 'POLYLINE':  # keep the dummy origin at 0,0
        i = b.index('10'); b[i + 1] = '0'; b[i + 3] = '0'
    return b


def _bbox(b):
    pts = _xy(b)
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def _inside(b, bb, tol=0.5):
    return all(bb[0] - tol <= x <= bb[2] + tol and bb[1] - tol <= y <= bb[3] + tol for x, y in _xy(b))


def _part_blocks(blocks, label_prefix):
    """The contour of the part whose label starts with label_prefix, and every entity lying inside it."""
    txt = [b for b in blocks if b[1] == 'TEXT' and b[b.index('1', 2) + 1].startswith(label_prefix)][0]
    tx, ty = _xy(txt)[0]
    cont = [b for b in blocks if b[1] == 'POLYLINE' and _layer(b).startswith('10_KONTUR')
            and _bbox(b)[0] <= tx <= _bbox(b)[2] and _bbox(b)[1] <= ty <= _bbox(b)[3]][0]
    bb = _bbox(cont)
    return [b for b in blocks if not _layer(b).startswith('00_') and _inside(b, bb)]


def _text_idx(b):
    for k in range(2, len(b) - 1, 2):
        if b[k] == '1':
            return k + 1


# ------------------------------------------------------------------------------- designer / input errors
def h01(P, S):
    # slide holes on the right face of the middle wall typed with a +3 mm vertical offset
    S['korpus_hull_alternativ'] = [[x, 3] for x, _ in S['korpus_hull_alternativ']]


def h02(P, S):
    P['front']['fuge'] = 0


def h03(P, S):
    P['korpus']['bunnlist_y'] = [70, 281]


def h04(P, S):
    # fixing screws moved onto the handle bolt line (box y=60 is the front's vertical centre)
    P['skuff']['front_skrue_x_inn'] = 259
    P['skuff']['front_skrue_y'] = [60, 90]


def h05(P, S):
    P['skuff']['not_fra_underkant'] = 3


def h06(P, S):
    P['skuff']['not_klaring'] = -0.3


def h07(P, S):
    P['tykkelse_malt']['skuff'] = 15.8   # nominal stays 19: the 16 mm offcut was measured, not the drawer board


def h08(P, S):
    P['korpus']['plugg_inn_fra_kant'] = 60   # dowel 10 mm c/c from the Minifix bolt at 50


def h09(P, S):
    for r in ('front', 'ytre'):
        P['_valg'][r] = dict(P['_valg'][r], retning=False)


# --------------------------------------------------------------------------------------- generator bugs
def h10(parts, asm, info):
    c = _p(parts, 'C')
    for o in c['ops']:
        if 'kinne' in o['note']:
            o['x'] = round(c['L'] - o['x'], 2)


def h11(parts, asm, info):
    for o in _p(parts, 'S')['ops']:
        if 'Skinne-pilot' in o['note']:
            o['y'] = round(o['y'] + 12, 2)


def h12(parts, asm, info):
    a = _p(parts, 'A')
    for o in a['ops']:
        if o['kind'] == 'hole':
            o['y'] = round(o['y'] - info['OV'], 2)


def h13(parts, asm, info):
    b = _p(parts, 'B')
    for o in b['ops']:
        if 'Minifix-hus' in o['note']:
            o['x'] = 34 if o['x'] < b['L'] / 2 else round(b['L'] - 34, 2)


def h14(parts, asm, info):
    d = _p(parts, 'D')
    d['B'] = round(d['B'] + info['T'], 2)
    for o in d['ops']:
        if 'mot topp' in o.get('note', ''):
            o['y'] = round(o['y'] + info['T'], 2)


def h15(parts, asm, info):
    sb = _p(parts, 'SB')
    sb['L'] = round(sb['L'] + 2, 2); sb['B'] = round(sb['B'] + 2, 2)


def h16(parts, asm, info):
    for code in ('E1', 'E2', 'SB'):
        p = _p(parts, code)
        half = p['L'] / 2
        p['L'] = round(p['L'] + 2, 2)
        for o in p['ops']:
            if 'x' in o and o['x'] > half:
                o['x'] = round(o['x'] + 2, 2)


def h17(parts, asm, info):
    _p(parts, 'K')['qty'] -= 1


# ---------------------------------------------------------------------------------- export / file faults
def h18(files):
    k = _sheet(files, 'plate3_')
    h, bl, t = _split(files[k])
    files[k] = _join(h, [_map(b, lambda v: v / 25.4, lambda v: v / 25.4, lambda v: v / 25.4) for b in bl], t)


def h19(files):
    k = _sheet(files, 'plate1_')
    files[k] = re.sub(r'03_LOMME_D15_Z[0-9P]+', '03_LOMME_D15_Z18P8', files[k])


def h20(files):
    k = _sheet(files, 'plate3_')
    files[k] = files[k].replace('10_KONTUR_UTVENDIG_Z18P8', '10_KONTUR_UTVENDIG_Z16')


def h21(files):
    k = _sheet(files, 'plate4_')
    h, bl, t = _split(files[k])
    gone = _part_blocks(bl, 'E2 ')
    files[k] = _join(h, [b for b in bl if not any(b is g for g in gone)], t)


def h22(files):
    k = _sheet(files, 'plate1_')
    h, bl, t = _split(files[k])
    W = float(re.search(r'_(\d+)x(\d+)\.dxf$', k).group(1))
    conts = [b for b in bl if _layer(b).startswith('10_KONTUR')]
    right = max(conts, key=lambda b: _bbox(b)[2])
    bb = _bbox(right)
    dx = W + 40 - bb[2]
    grp = [b for b in bl if not _layer(b).startswith('00_') and _inside(b, bb)]
    bl = [_map(b, fx=lambda v: v + dx) if any(b is g for g in grp) else b for b in bl]
    files[k] = _join(h, bl, t)


def h23(files):
    k = _sheet(files, 'plate1_')
    H = float(re.search(r'_(\d+)x(\d+)\.dxf$', k).group(2))
    h, bl, t = _split(files[k])
    files[k] = _join(h, [b if _layer(b).startswith('00_') else _map(b, fy=lambda v: H - v) for b in bl], t)


def h24(files):
    k = _sheet(files, 'plate1_')
    h, bl, t = _split(files[k])
    files[k] = _join(h, [_map(b, fr=lambda r: 2 * r) if b[1] == 'CIRCLE' and _layer(b).startswith('01_BOR') else b
                         for b in bl], t)


def h25(files):
    # the sheet that holds both an E1 and an E2 (which sheet depends on the nesting)
    def has(k, code):
        return any(b[1] == 'TEXT' and b[_text_idx(b)].startswith(code + ' ') for b in _split(files[k])[1])
    k = next(k for k in sorted(files) if k.endswith('.dxf') and has(k, 'E1') and has(k, 'E2'))
    h, bl, t = _split(files[k])
    tx = [b for b in bl if b[1] == 'TEXT']
    a = [b for b in tx if b[_text_idx(b)].startswith('E1 ')][0]
    c = [b for b in tx if b[_text_idx(b)].startswith('E2 ')][0]
    ia, ic = _text_idx(a), _text_idx(c)
    a[ia], c[ic] = c[ic], a[ia]
    files[k] = _join(h, bl, t)


FAULTS = [
    # designer / input
    Fault('h01', 'Slide holes on middle wall 3 mm higher than on the opposite side',
          'Each drawer hangs on two slides; if the carcass members are not at the same height the box is twisted, '
          'the ball cages bind and the drawer racks or drops off one rail. Hettich/Blum: both runners in one plane, tolerance <=0.5 mm.',
          params=h01, source='Hettich KA/Quadro mounting instructions; System 32 line-boring practice'),
    Fault('h02', 'Zero gap (fuge) between drawer fronts',
          'Fronts touch: edge banding rubs, ABS chips, fronts cannot open past each other and any 0.5 mm swelling '
          'or slide sag locks the stack. Overlay fronts need 2-3 mm reveals.',
          params=h02, source='Kitchen/overlay front reveal rules (Blum: 2-3 mm gap)'),
    Fault('h03', 'Plinth strip placed on top of the leg mounting positions',
          'Bunnlist at y=70..89 runs straight through the 40x40 leg plates at y=60..100 near both ends: legs cannot '
          'be screwed on, or the strip must be notched by hand.',
          params=h03, source='Leg/plinth layout under carcass bottoms (Ikea/Hafele leg plates)'),
    Fault('h04', 'Front fixing screws placed exactly on the handle bolt line',
          'The 4x30 screw through the drawer end sits where the handle M4 bolt has to pass (front centre, 96 mm off '
          'centre): the bolt hits the screw, the handle cannot be fitted.',
          params=h04, source='Drawer front attachment practice: keep fixing screws clear of handle bores'),
    Fault('h05', 'Bottom groove only 3 mm above lower edge of drawer parts',
          'A 3 mm strip of particleboard under a 6.4 mm groove breaks off when the router passes or when the loaded '
          'HDF bottom pushes down. Typical minimum 8-12 mm.',
          params=h05, source='Drawer box construction (groove 10-12 mm up), particleboard edge strength'),
    Fault('h06', 'Groove clearance typed with a minus sign: groove narrower than the HDF',
          'Groove 5.6 mm for a 5.9 mm bottom: the bottom cannot be slid in; forcing it splits the groove lips.',
          params=h06, source='Sign/typo error in parameters; groove must be board + 0.3-0.5 mm'),
    Fault('h07', 'Drawer board thickness measured on the wrong (16 mm) sheet',
          'Measured 15.8 on a nominal 19 board: every drawer end is 6 mm too long, boxes are too wide for the slide '
          'clearance, grooves and confirmat positions are wrong. A >3 mm deviation is a measurement mix-up, not tolerance.',
          params=h07, source='Measuring the wrong offcut/sample; sheet-goods thickness tolerance is +-0.3 mm'),
    Fault('h08', 'Dowel only 10 mm from the Minifix bolt',
          'Ø8 dowel at 60 next to Ø5 Minifix bolt at 50: 3.5 mm web between bores on the face and on the end edge; '
          'the particleboard between them crumbles and neither fitting holds.',
          params=h08, source='Hafele/Hettich connector spacing: keep >=32 mm (System 32) between connector and dowel'),
    Fault('h09', 'Oak decor grain flag lost: fronts/top/sides nested rotated',
          'Kaindl Eik Dew has a grain direction; with retning=False the nester rotates parts freely - here the right '
          'side CH is nested turned 90 deg, so its grain runs vertically while the left side runs horizontally. '
          'Visible on the finished piece, cannot be fixed after cutting.',
          params=h09, source='Decor/veneer grain direction in nesting software (grain lock)'),
    # generator bugs
    Fault('h10', 'Side panel slide holes referenced from the back edge',
          'Slide pilots on the left side C at DEP-x instead of x from the front (C now looks like the mirrored CH): the '
          'left runners sit ~36 mm further back than the middle-wall runners, the drawer cannot be mounted square and '
          'the front will not close flush.',
          parts=h10, source='Wrong reference edge / origin in CNC programs (front-edge reference for slides)'),
    Fault('h11', 'Drawer-side slide holes 12 mm too low on the box',
          'Box-member holes on the left drawer sides (S) are 12 mm off the box centre while the right sides (SH) are '
          'correct: every box hangs tilted, the bottom drawer drags on the carcass bottom and fronts are skewed.',
          parts=h11, source='Box-member mounting height vs cabinet-member height (Hettich/Blum)'),
    Fault('h12', 'Top dowel/Minifix holes miss the front overhang offset',
          'Holes in the top ignore the 21 mm overhang: the top sits flush with the carcass front, so the 18.8 mm '
          'drawer fronts stand proud of the top and the top hangs 24 mm over the back.',
          parts=h12, source='Offset/reference error between mating parts (top vs side edge bores)'),
    Fault('h13', 'Minifix cam housings in the bottom at 34 mm instead of 24 mm',
          'The cam must sit at the bolt-head distance (24 mm for this bolt). At 34 mm the bolt head does not reach '
          'the cam: no clamping, the carcass joint is loose.',
          parts=h13, source='Hafele Minifix 15 drilling data (dimension B = 24 mm)'),
    Fault('h14', 'Middle wall cut full side height (bottom thickness not subtracted)',
          'Middle wall stands on the bottom but is cut 653 mm: 18.8 mm too tall, the top cannot come down onto the '
          'sides and all Minifix joints at the top stay open.',
          parts=h14, source='Classic carcass arithmetic error (forgot one board thickness)'),
    Fault('h15', 'Drawer bottom 2 mm too large in both directions',
          'Bottom is 1 mm per side deeper than the groove bottoms: the box cannot be closed, or is forced out of '
          'square / bows the sides.',
          parts=h15, source='Panel-in-groove sizing (groove depth minus play)'),
    Fault('h16', 'Drawer box 2 mm too wide for the slides',
          'Ends/bottom 2 mm long: 1 mm less than the 12.7 mm slide clearance per side. Ball-bearing slides tolerate '
          '+-0.2 mm; the drawer jams or the slide must be forced.',
          parts=h16, source='Hettich KA 4532 / Accuride: side clearance 12.7 +0.2/-0'),
    Fault('h17', 'Only 7 drawer fronts generated for 8 drawers',
          'Off-by-one in quantity: cut list and sheets both say 7, one drawer has no front. Found at assembly, a '
          'second oak sheet run for one part.',
          parts=h17, source='Off-by-one quantity bugs in cut lists'),
    # export / file faults
    Fault('h18', 'Sheet exported in inches but header still says mm',
          'All coordinates on the drawer-parts sheet are 25.4x too small while $INSUNITS=4 (mm). The CAM imports '
          'tiny parts; if scaled by guess, everything is off.',
          dxf=h18, source='DXF unit mismatch (VCarve/ShopBot import scale)'),
    Fault('h19', 'Minifix housing pockets drilled through the oak sides',
          'Layer depth for Ø15 cam housings written as Z18.8 (full thickness) instead of Z13.5: Ø15 holes through the '
          'visible outside of both side panels.',
          dxf=h19, source='Layer-encoded depth errors in CAM templates'),
    Fault('h20', 'Contour depth set for 16 mm board on 18.8 mm sheet',
          'Profile depth Z16 leaves 2.8 mm uncut: parts are not freed, have to be broken/cut out by hand, edges '
          'chip and the parts may shift during later ops.',
          dxf=h20, source='Reusing a toolpath template from a thinner material'),
    Fault('h21', 'One drawer back (E2) missing from its sheet',
          'Sheet has 7 E2 while the cut list says 8: one box has no back, second machine run.',
          dxf=h21, source='Part count on sheet vs cut list mismatch (manual nest edit)'),
    Fault('h22', 'Part placed beyond the sheet edge',
          'The rightmost part on the oak sheet extends 40 mm past the 2440 mm sheet: the bit cuts air or the '
          'clamps/bed, part comes out short.',
          dxf=h22, source='Manual nest edits / bed size mismatch'),
    Fault('h23', 'Oak sheet exported mirrored (Y flipped)',
          'All hole patterns are mirrored inside their parts (origin top-left vs bottom-left): top dowels at the wrong '
          'distance from the front, slide holes top/bottom swapped on the sides.',
          dxf=h23, source='Mirror/flip on DXF export or wrong CAM origin corner'),
    Fault('h24', 'Blind holes exported with radius = diameter',
          'Circles on 01_BOR layers are twice the size: Ø5 Minifix bolt bores become Ø10, Ø8 dowels Ø16 - nothing '
          'holds, and the CAM may pocket them.',
          dxf=h24, source='Radius/diameter confusion in DXF writers'),
    Fault('h25', 'Labels swapped between a front end (E1) and a back end (E2)',
          'The part labelled E1 has no front fixing holes and the one labelled E2 has them: built into the wrong '
          'position, the front cannot be screwed on.',
          dxf=h25, source='Mislabelled parts on nested sheets'),
]
