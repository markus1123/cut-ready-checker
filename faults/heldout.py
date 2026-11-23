"""Held-out set 2: blind red-team faults (x01-x25). Written without looking at the checker."""
import re
from fc.core import Fault


# ------------------------------------------------------------------------------------------ helpers
def _p(parts, code):
    return [p for p in parts if p['code'] == code][0]


def _sheets(files, pat=None):
    ks = sorted(files)
    return [k for k in ks if (pat is None or re.search(pat, k))]


def _busiest(files, layer_pat):
    """The sheet file with the most entities on a layer matching layer_pat."""
    best, n = None, -1
    for k in sorted(files):
        c = len(re.findall(r'\n8\n' + layer_pat, files[k]))
        if c > n:
            best, n = k, c
    if n <= 0:
        raise ValueError('no sheet with layer ' + layer_pat)
    return best


def _polys(lines, layer_pat):
    """Yield (start, [vertex line indices of the 10/20 codes]) for POLYLINEs on a matching layer."""
    out = []
    i = 0
    n = len(lines)
    while i < n - 3:
        if lines[i] == '0' and lines[i + 1] == 'POLYLINE' and lines[i + 2] == '8' and re.match(layer_pat, lines[i + 3]):
            verts, j = [], i + 2
            while not (lines[j] == '0' and lines[j + 1] == 'SEQEND'):
                if lines[j] == '0' and lines[j + 1] == 'VERTEX':
                    k, xi, yi = j + 2, None, None
                    while lines[k] != '0':
                        if lines[k] == '10': xi = k + 1
                        if lines[k] == '20': yi = k + 1
                        k += 2
                    verts.append((xi, yi))
                    j = k
                else:
                    j += 2
            out.append((i, verts))
            i = j
        i += 2
    return out


def _kontur_layer(text):
    m = re.search(r'\n8\n(10_KONTUR[^\n]*)\n', text)
    if not m:
        raise ValueError('no contour layer')
    return m.group(1)


# ------------------------------------------------------------------------------------------ params
def x01(P, S):
    # drawer box height typed as the front height + a bit -> taller than the row pitch
    F = P['front']
    fh = (P['ytre']['hoyde_side'] - 2 * F['kant_topp_bunn'] - (P['rader'] - 1) * F['fuge']) / P['rader']
    P['skuff']['hoyde'] = round(fh + F['fuge'] + 12)


def x02(P, S):
    P['ytre']['topp_overheng_front'] = -abs(P['ytre']['topp_overheng_front'] or 21)


def x03(P, S):
    src = P['_valg']['skuffebunn']
    P['materialvalg']['skuff'] = src['id']
    P['_valg']['skuff'] = dict(src)
    P['tykkelse_malt']['skuff'] = P['tykkelse_malt']['skuffebunn']
    P['tykkelse_nominell']['skuff'] = P['tykkelse_nominell']['skuffebunn']


def x04(P, S):
    P['verksted']['marg_platekant'] = 0


def x05(P, S):
    P['verksted']['fres_liten_skjaerlengde'] = 38.0   # overall length of the 1/8" bit typed as flute length


def x06(P, S):
    P['korpus']['bunnlist_hoyde'] = P['ytre']['beinhoyde'] + 12


def x07(P, S):
    P['skuff']['bunn_spill_per_side'] = P['skuff']['not_dybde'] + 1   # 9 typed for 0.9


def x08(P, S):
    S['pilot_d'] = 6.0


def x09(P, S):
    P['skuff']['senter_over_frontsenter'] = -70   # meant -7


# ------------------------------------------------------------------------------------------ parts
def x10(parts, asm, info):
    for o in _p(parts, 'K')['ops']:
        if 'x' in o and 'y' in o:
            o['x'], o['y'] = o['y'], o['x']


def x11(parts, asm, info):
    ch = _p(parts, 'CH')
    swap = {'kant:overkant': 'kant:underkant', 'kant:underkant': 'kant:overkant'}
    ops = []
    for o in _p(parts, 'C')['ops']:
        o = dict(o)
        if 'y' in o:
            o['y'] = round(ch['B'] - o['y'], 2)
        if o['kind'] == 'edge' and o['face'] in swap:
            o['face'] = swap[o['face']]
        ops.append(o)
    ch['ops'] = ops


def x12(parts, asm, info):
    d = _p(parts, 'D')
    a = sorted({o['x'] for o in d['ops'] if o.get('screw_face') == 'F1'})
    b = sorted({o['x'] for o in d['ops'] if o.get('screw_face') == 'F2'})
    m = dict(zip(b, a))
    for o in d['ops']:
        if o.get('screw_face') == 'F2':
            o['x'] = m[o['x']]


def x13(parts, asm, info):
    sh = _p(parts, 'SH')
    sh['ops'] = [o for o in sh['ops'] if o['kind'] != 'groove']


def x14(parts, asm, info):
    for o in _p(parts, 'B')['ops']:
        if o['kind'] == 'through':
            o['y'] = round(o['y'] + info['T'], 2)


def x15(parts, asm, info):
    k = _p(parts, 'K')
    k['L'] = round(info['W'], 2)


def x16(parts, asm, info):
    _p(parts, 'SB')['mat'] = _p(parts, 'S')['mat']


def x17(parts, asm, info):
    for o in _p(parts, 'A')['ops']:
        if o.get('face') == 'F1':
            o['face'] = 'F2'


# ------------------------------------------------------------------------------------------ dxf
def x18(files):
    for k in files:
        files[k] = re.sub(r'(\n0\nPOLYLINE\n8\n10_KONTUR[^\n]*\n66\n1\n70\n)1\n', r'\g<1>0\n', files[k])


def x19(files):
    k = _busiest(files, '10_KONTUR')
    files[k] = re.sub(r'(?m)^10_KONTUR[^\n]*$', '0', files[k])


def x20(files):
    k = _busiest(files, '99_TEKST')
    lay = _kontur_layer(files[k])
    files[k] = files[k].replace('\n0\nTEXT\n8\n99_TEKST\n', '\n0\nTEXT\n8\n%s\n' % lay)


def x21(files):
    k = _busiest(files, '04_NOT')
    lines = files[k].split('\n')
    polys = _polys(lines, r'04_NOT')
    if not polys:
        raise ValueError('no groove')
    for _, v in polys:
        xs = [float(lines[a]) for a, _ in v]; ys = [float(lines[b]) for _, b in v]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        pts = [(cx - h / 2, cy - w / 2), (cx + h / 2, cy - w / 2), (cx + h / 2, cy + w / 2), (cx - h / 2, cy + w / 2)]
        for (a, b), (x, y) in zip(v, pts):
            lines[a], lines[b] = '%.3f' % x, '%.3f' % y
    files[k] = '\n'.join(lines)


def x22(files):
    k = _busiest(files, '03_LOMME')
    files[k] = re.sub(r'(?m)^03_LOMME_D[^_\n]+_Z([^\n]+)$', r'01_BOR_D5_Z\1', files[k])


def x23(files):
    k = _busiest(files, '10_KONTUR')
    files[k] = re.sub(r'KONTUR_UT\w*?(_Z)', r'KONTUR_INNVENDIG\1', files[k])


def x24(files):
    # the largest part on the busiest sheet: vertices 3 and 4 swapped -> bow-tie contour
    k = _busiest(files, '10_KONTUR')
    lines = files[k].split('\n')
    polys = _polys(lines, r'10_KONTUR')
    def area(v):
        xs = [float(lines[a]) for a, _ in v]; ys = [float(lines[b]) for _, b in v]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))
    _, v = max(polys, key=lambda t: area(t[1]))
    (a2, b2), (a3, b3) = v[2], v[3]
    lines[a2], lines[a3] = lines[a3], lines[a2]
    lines[b2], lines[b3] = lines[b3], lines[b2]
    files[k] = '\n'.join(lines)


def x25(files):
    # two sheet files of the same size but different board: contents swapped on export/upload
    groups = {}
    for k in sorted(files):
        m = re.match(r'^[a-z]+\d+_(.+)_(\d+x\d+)\.dxf$', k)
        if m:
            groups.setdefault(m.group(2), []).append((m.group(1), k))
    for size, lst in sorted(groups.items()):
        mats = {}
        for mat, k in lst:
            mats.setdefault(mat, k)
        # prefer an oak/decor sheet vs a plain one with the same thickness class
        ks = list(mats.values())
        thick = [k for k in ks if re.search(r'KONTUR[^\n]*_Z1\d', files[k])]
        if len(thick) >= 2:
            a, b = thick[0], thick[1]
            files[a], files[b] = files[b], files[a]
            return
    raise ValueError('no pair of same-size sheets in different boards')


FAULTS = [
    Fault('x01', 'Drawer box height typed from the front height: box taller than the row pitch',
          'Each drawer box is taller than the distance between slide rows, so the boxes of neighbouring rows collide; '
          'the drawers cannot be installed together and the cut drawer sides/ends are scrap.',
          params=x01, source='designer typed front height (+ clearance) into the box-height field'),
    Fault('x02', 'Top overhang entered with a minus sign: top shallower than the carcass',
          'The top is cut ~40 mm short in depth, so it stops 21 mm behind the front edge of the sides and does not cover '
          'the back panel; the oak top is scrap and the carcass cannot be finished.',
          params=x02, source='sign error on an offset field (overhang vs setback)'),
    Fault('x03', 'Drawer boxes assigned to 6 mm hardboard instead of 19 mm chipboard',
          'Drawer sides/ends come out of 5.9 mm hardboard: 8 mm bottom grooves cut through, Ø7 confirmat screws cannot '
          'hold in 6 mm board and the slides cannot be screwed on. All drawer boxes are scrap.',
          params=x03, source='wrong material picked from the drop-down for one role'),
    Fault('x04', 'Sheet edge margin set to 0 mm',
          'Parts are nested right up to the raw sheet edge where the hold-down clamps/screws are; the bit runs into '
          'the clamps (broken bit, possible projectile) and the chipped factory edge ends up on visible parts.',
          params=x04, source='nesting margin zeroed to squeeze one more part on the sheet'),
    Fault('x05', '1/8" bit flute length entered as 38 mm (overall length)',
          'Small through holes are no longer spot-drilled: the CNC plunges a 3.175 mm bit with a 12.7 mm flute '
          'through 18.8 mm board, the shank burns in and the bit snaps.',
          params=x05, source='tool table: overall length typed in the cutting-length field'),
    Fault('x06', 'Plinth strip taller than the legs',
          'The plinth strips hang 12 mm below the feet, so the kommode stands on the strips, rocks, and the legs never '
          'touch the floor; the strips (and screw holes in the bottom) must be remade.',
          params=x06, source='plinth height chosen without checking the leg height'),
    Fault('x07', 'Drawer bottom play per side typed as 9 mm (meant 0.9)',
          'The bottom is smaller than the span between the groove bottoms minus the groove depth, so it does not '
          'engage the grooves at all and drops out of every drawer.',
          params=x07, source='missing decimal point in a clearance field'),
    Fault('x08', 'Slide pilot hole diameter set to 6 mm for Ø4 screws',
          'The slide pilot holes are larger than the Ø4 slide screws; the screws spin freely, the slides cannot be '
          'fixed and every side, middle wall and drawer side is drilled wrong.',
          params=x08, source='screw head/washer diameter typed as pilot diameter'),
    Fault('x09', 'Drawer centre offset over front centre typed -70 (meant -7)',
          'Drawer boxes and slides move 70 mm down: the bottom drawer box/slide sits below the carcass bottom and every '
          'slide row is misaligned with its front, so no drawer can be mounted.',
          params=x09, source='missing decimal point / unit slip in an offset field'),
    Fault('x10', 'Generator bug: handle hole x/y swapped on the fronts',
          'Handle holes are placed at y = 304/496 on a 160 mm high front, i.e. off the part; the CNC drills into the '
          'neighbouring part or spoilboard and the fronts get no (correct) handle holes.',
          parts=x10, source='axis swap in a coordinate transform'),
    Fault('x11', 'Generator bug: right side CH mirrored top-bottom instead of front-back',
          'The right side gets its slide holes and joint holes flipped vertically: the right slides sit at different '
          'heights from the left ones and the Minifix housings land at the bottom. The oak side is scrap.',
          parts=x11, source='mirror about the wrong axis when deriving the handed part'),
    Fault('x12', 'Generator bug: middle wall uses the same slide hole pattern on both faces',
          'The left-face slide holes are drilled at the same x as the right-face ones, so 12.8 mm screws from both '
          'sides meet in an 18.8 mm wall; the screws collide/split the wall and one side of slides cannot be fixed.',
          parts=x12, source='alternate hole pattern for the opposite face ignored'),
    Fault('x13', 'Generator bug: mirrored right drawer side SH has no bottom groove',
          'Right drawer sides are cut without the groove for the drawer bottom, so the bottom cannot be slid in and '
          'the drawers cannot be assembled.',
          parts=x13, source='operation dropped when copying/mirroring a part'),
    Fault('x14', 'Generator bug: plinth screw holes in the bottom offset by one board thickness',
          'The holes for the plinth screws land beside the plinth strips instead of over their centre line; '
          'screws go into air and the plinth cannot be fixed.',
          parts=x14, source='reference edge vs centre-line mix-up for mating hole pattern'),
    Fault('x15', 'Generator bug: drawer front width ignores the number of columns',
          'Every drawer front is cut the full width of the kommode instead of half; fronts overlap each other, '
          'handle holes are off-centre, and 8 oak fronts are scrap.',
          parts=x15, source='division by column count lost in a refactor'),
    Fault('x16', 'Generator bug: drawer bottoms nested on the 19 mm drawer-side board',
          'The drawer bottoms are cut out of 18.8 mm chipboard instead of 6 mm hardboard; they cannot enter the '
          '6.4 mm grooves, and the shared sheet gets the wrong contour depth for one of the thicknesses.',
          parts=x16, source='material/role mapping bug in the part list'),
    Fault('x17', 'Generator bug: top joint holes placed on the visible upper face',
          'Minifix bolt and dowel holes are specified on the oak top\'s show face instead of the underside; they are '
          'drilled into the visible surface and the top is ruined.',
          parts=x17, source='face flag (F1/F2) inverted for one part'),
    Fault('x18', 'DXF: contour polylines exported open (closed flag cleared)',
          'CAM treats the outlines as open chains: no inside/outside offset can be applied, the last edge is not '
          'cut, and parts are either cut on the line (undersize) or not released.',
          dxf=x18, source='DXF exporter writes POLYLINE flag 70=0 instead of 1'),
    Fault('x19', 'DXF: contours on one sheet exported on layer "0"',
          'The CAM template maps tools and depths by layer; the outlines on layer 0 get no profile toolpath (or a '
          'default engrave), so the sheet is drilled but the parts are never cut out, or cut at the wrong depth.',
          dxf=x19, source='layer names dropped on export (everything to layer 0)'),
    Fault('x20', 'DXF: part labels exported on the contour layer',
          'The label text is on the through-cut layer, so the CNC routes the letters full depth into the faces of '
          'every part on that sheet: parts ruined.',
          dxf=x20, source='text entities assigned to the wrong layer'),
    Fault('x21', 'DXF: bottom grooves drawn across the part instead of along it',
          'The groove rectangles are rotated 90 degrees: the 8 mm deep groove runs across the drawer parts and into '
          'their neighbours, cutting them in two.',
          dxf=x21, source='groove not rotated together with a rotated part in the nester'),
    Fault('x22', 'DXF: Minifix housing circles exported on a Ø5 drill layer',
          'The CAM drills the 15 mm housings with a 5 mm drill cycle at the centre; the Minifix cams do not fit and '
          'the carcass cannot be assembled.',
          dxf=x22, source='layer mapping: pocket circles assigned to a drill layer'),
    Fault('x23', 'DXF: outer contours on one sheet exported as inside contours',
          'Tool compensation goes to the inside of the line, so every part on the sheet comes out one bit diameter '
          '(6.35 mm) too small in both directions.',
          dxf=x23, source='wrong layer suffix/tool-side in the export template'),
    Fault('x24', 'DXF: largest contour on a sheet has two vertices swapped (bow-tie)',
          'The outline self-intersects; CAM cannot offset it, or cuts a diagonal straight through the part.',
          dxf=x24, source='vertex order corrupted on export'),
    Fault('x25', 'DXF: two same-size sheet files for different boards have swapped contents',
          'The operator loads the oak sheet and cuts the white carcass parts on it (and vice versa): wrong decor on '
          'fronts/sides and both sheets wasted.',
          dxf=x25, source='file names and contents mixed up when exporting/uploading per material'),
]

VERSION = 2   # second blind held-out set, written after v1 was retired
