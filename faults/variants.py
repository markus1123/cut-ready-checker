"""Variants of practice faults written by the loop variant agent (blind to the rule under test)."""
import re
from fc.core import Fault  # noqa: F401

FAULTS = []


# ------------------------------------------------------------------ variants of y02 (Minifix bolt pilot diameter)
def _v_y02_1(P, S):
    P['korpus']['minifix_bolt_d'] = 7


def _v_y02_2(P, S):
    P['korpus']['minifix_bolt_d'] = 3


def _v_y02_3(P, S):
    K = P['korpus']
    K['minifix_bolt_d'], K['plugg_d'] = K['plugg_d'], K['minifix_bolt_d']


# ------------------------------------------------------------------ variants of y07 (front-fixing hole size)
def _v_y07_1(P, S):
    P['front']['justerbar_feste'] = True
    P['front']['festehull_d_justerbar'] = 10


def _v_y07_2(P, S):
    P['front']['justerbar_feste'] = False
    P['front']['festehull_d_fast'] = 12


def _v_y07_3(P, S):
    P['front']['justerbar_feste'] = True
    P['front']['festehull_d_justerbar'] = 3


# ------------------------------------------------------------------ variants of y13 (missing handle hole)
def _handle_ops(p):
    return [o for o in p['ops'] if 'åndtak' in o['note']]


def _v_y13_1(parts, asm, info):
    for p in parts:
        if p['code'] == 'K':
            hh = sorted(_handle_ops(p), key=lambda o: o['x'])
            p['ops'].remove(hh[0])


def _v_y13_2(parts, asm, info):
    for p in parts:
        if p['code'] == 'K':
            hh = sorted(_handle_ops(p), key=lambda o: o['x'])
            hh[1]['x'] = hh[0]['x']


def _v_y13_3(parts, asm, info):
    for p in parts:
        if p['code'] == 'K':
            for o in _handle_ops(p):
                p['ops'].remove(o)


FAULTS += [
    Fault('v_y02_1', 'Minifix bolt pilot holes set to Ø7 instead of Ø5',
          'The Minifix bolts spin loose in Ø7 holes - the thread barely touches the chipboard, so top, bottom and middle-wall joints cannot be tightened.',
          params=_v_y02_1, source='variant of y02: oversize bolt pilot, smaller magnitude'),
    Fault('v_y02_2', 'Minifix bolt pilot holes set to Ø3 instead of Ø5',
          'The bolts cannot be screwed into Ø3 pilots without splitting the chipboard around every joint; the bolts stand proud and the cams do not lock.',
          params=_v_y02_2, source='variant of y02: undersize bolt pilot'),
    Fault('v_y02_3', 'Minifix bolt and dowel diameters swapped (bolt Ø8, dowel Ø5)',
          'Every bolt hole is Ø8 (no bite), every Ø8 dowel meets a Ø5 hole and the edge bores for bolts/dowels are Ø5: neither dowels nor bolts fit anywhere in the carcass.',
          params=_v_y02_3, source='variant of y02: two joinery fields swapped'),
    Fault('v_y07_1', 'Adjustable front-fixing holes in the drawer front ends set to Ø10',
          'A standard M4/4 mm washer (Ø9) slips through a Ø10 hole, so the 4x30 screws cannot clamp the fronts to the drawer boxes.',
          params=_v_y07_1, source='variant of y07: oversize adjustable hole, smaller magnitude'),
    Fault('v_y07_2', 'Fixed (non-adjustable) front-fixing holes set to Ø12 instead of Ø4',
          'With fixed fixing selected the holes should just clear the 4 mm screw; at Ø12 screw head and washer pull through and the fronts cannot be fastened.',
          params=_v_y07_2, source='variant of y07: same mistake in the fixed-hole field'),
    Fault('v_y07_3', 'Adjustable front-fixing holes set to Ø3 (smaller than the 4 mm screw)',
          'The 4x30 screws bind in the drawer end instead of passing through, so they jack the front away instead of pulling it tight, and there is no adjustment at all.',
          params=_v_y07_3, source='variant of y07: undersize instead of oversize'),
    Fault('v_y13_1', 'Generator bug: left handle hole dropped on every drawer front',
          'Only the right-hand bolt hole is drilled; two-bolt bar handles cannot be fitted and hand-drilling the missing hole in finished oak fronts gives misaligned handles.',
          parts=_v_y13_1, source='variant of y13: off-by-one drops the first hole instead of the last'),
    Fault('v_y13_2', 'Generator bug: both handle holes drilled at the same position on every front',
          'The two handle ops collapse onto the left hole position: each front gets a single hole, so the 192 c/c handle cannot be mounted.',
          parts=_v_y13_2, source='variant of y13: second hole copied from the first (c/c lost)'),
    Fault('v_y13_3', 'Generator bug: no handle holes at all on the drawer fronts',
          'Fronts are cut without any handle holes; all eight oak fronts would have to be marked and drilled by hand after finishing.',
          parts=_v_y13_3, source='variant of y13: whole handle-op list dropped'),
]


# ------------------------------------------------------------------ variants of y10 (one dimension from the wrong variable)
def _v_y10_1(parts, asm, info):
    for p in parts:
        if p['code'] == 'G':
            p['B'] = round(info['HS'] - info['T'], 2)      # middle-wall height (HS - T) instead of side height


def _v_y10_2(parts, asm, info):
    for p in parts:
        if p['code'] == 'G':
            p['L'] = info['DEP']                           # width from carcass depth instead of outer width


def _v_y10_3(parts, asm, info):
    for p in parts:
        if p['code'] == 'D':
            p['B'] = info['DEP']                           # middle wall height from carcass depth instead of HS - T


# ------------------------------------------------------------------ variants of v_y02_3 (two joinery fields swapped)
def _v_v_y02_3_1(P, S):
    K = P['korpus']
    K['minifix_bolt_d'], K['minifix_hus_d'] = K['minifix_hus_d'], K['minifix_bolt_d']


def _v_v_y02_3_2(P, S):
    K = P['korpus']
    K['plugg_dybde_flate'], K['plugg_dybde_kant'] = K['plugg_dybde_kant'], K['plugg_dybde_flate']


def _v_v_y02_3_3(P, S):
    K = P['korpus']
    K['minifix_kanthull_dybde'], K['plugg_dybde_kant'] = K['plugg_dybde_kant'], K['minifix_kanthull_dybde']


# ------------------------------------------------------------------ variants of v_y13_3 (whole op group dropped from a part)
def _drop_ops(parts, codes, pred):
    for p in parts:
        if p['code'] in codes:
            p['ops'] = [o for o in p['ops'] if not pred(o)]


def _v_v_y13_3_1(parts, asm, info):
    _drop_ops(parts, ('S', 'SH'), lambda o: 'Konfirmat' in o.get('note', ''))


def _v_v_y13_3_2(parts, asm, info):
    _drop_ops(parts, ('C', 'CH'), lambda o: 'kinne' in o.get('note', ''))


def _v_v_y13_3_3(parts, asm, info):
    _drop_ops(parts, ('A',), lambda o: o.get('kind') == 'hole')


FAULTS += [
    Fault('v_y10_1', 'Generator bug: back panel height taken from middle-wall height (HS - T) instead of side height',
          'The back panel is cut ~19 mm short: an open strip runs along the top at the back under the top, the carcass is not braced over its full height and the back panel cannot be nailed to the top edge of the sides.',
          parts=_v_y10_1, source='variant of y10: same part, wrong variable, small magnitude'),
    Fault('v_y10_2', 'Generator bug: back panel width taken from carcass depth (430) instead of outer width',
          'The back panel is cut 430 mm wide on a carcass more than twice that wide: most of the back is open, the carcass racks and the panel is scrap.',
          parts=_v_y10_2, source='variant of y10: other dimension of the same part'),
    Fault('v_y10_3', 'Generator bug: middle wall height taken from carcass depth (430) instead of HS - T',
          'The middle wall is cut ~200 mm too short: it cannot reach from the bottom to the top, the top Minifix housings and upper slide holes are missing/off the part and the upper drawers have nothing to run on.',
          parts=_v_y10_3, source='variant of y10: same wrong-variable bug on a different part'),
    Fault('v_v_y02_3_1', 'Minifix bolt and cam-housing diameters swapped (bolt Ø15, housing Ø5)',
          'Every bolt pilot becomes a Ø15 crater with nothing for the thread to bite, and every cam housing is a Ø5 hole the Ø15 cam cannot go into: no carcass joint can be assembled.',
          params=_v_v_y02_3_1, source='variant of v_y02_3: different pair of Minifix fields swapped'),
    Fault('v_v_y02_3_2', 'Dowel face depth and edge depth swapped (face 20 mm, edge 12 mm)',
          'The face dowel holes are drilled 20 mm deep in 18.8 mm board and blow out through the visible top/outside faces, while the 12 mm edge holes are too shallow for the dowels so the joints do not close.',
          params=_v_v_y02_3_2, source='variant of v_y02_3: swapped depths instead of diameters'),
    Fault('v_v_y02_3_3', 'Minifix edge-bore depth and dowel edge depth swapped (bolt bore 20 mm, dowel 34 mm)',
          'The 20 mm Minifix edge bore stops short of the cam housing 24 mm in, so the bolt can never reach the cam and the joint cannot be tightened; dowels sink into 34 mm holes.',
          params=_v_v_y02_3_3, source='variant of v_y02_3: two edge-depth fields swapped'),
    Fault('v_v_y13_3_1', 'Generator bug: no confirmat holes at all in the drawer sides',
          'Drawer sides are cut without the 7 mm confirmat holes; the boxes cannot be screwed together and hand-drilling them all square to the end grain is unrealistic.',
          parts=_v_v_y13_3_1, source='variant of v_y13_3: whole joinery op group dropped on the drawer sides'),
    Fault('v_v_y13_3_2', 'Generator bug: no slide pilot holes on the carcass sides',
          'The carcass sides are cut without any slide pilots: slides must be positioned by hand on finished sides, drawers end up at uneven heights and fronts do not line up.',
          parts=_v_v_y13_3_2, source='variant of v_y13_3: whole hardware op group dropped on another part'),
    Fault('v_v_y13_3_3', 'Generator bug: no bolt or dowel holes at all in the top',
          'The top is cut blank on the underside: no Minifix bolts or dowels can go in, so the top cannot be joined to the sides and middle wall.',
          parts=_v_v_y13_3_3, source='variant of v_y13_3: whole op list dropped on a carcass part'),
]


# ------------------------------------------------------------------ variants of y04 (machine bed entered too large)
def _v_y04_1(P, S):
    P['verksted']['plate_maks'] = [2500, 1220]     # only the long axis wrong (+60 mm)


def _v_y04_2(P, S):
    P['verksted']['plate_maks'] = [2440, 1250]     # only the short axis wrong (+30 mm)


def _v_y04_3(P, S):
    P['verksted']['plate_maks'] = [2800, 2070]     # the dealer's full chipboard format typed as the machine bed


# ------------------------------------------------------------------ variants of y23 (decimal marker corrupted in a layer name)
def _v_sheet_with(files, pat):
    return [k for k in sorted(files) if re.search(pat, files[k], re.M)][0]


def _v_y23_1(files):
    k = _v_sheet_with(files, r'^10_KONTUR_UTVENDIG_Z5P9$')
    files[k] = files[k].replace('10_KONTUR_UTVENDIG_Z5P9', '10_KONTUR_UTVENDIG_Z59')


def _v_y23_2(files):
    k = _v_sheet_with(files, r'^10_KONTUR_UTVENDIG_Z18P8$')
    files[k] = files[k].replace('10_KONTUR_UTVENDIG_Z18P8', '10_KONTUR_UTVENDIG_Z1P88')


def _v_y23_3(files):
    k = _v_sheet_with(files, r'^04_NOT_B6P4_Z8$')
    files[k] = files[k].replace('04_NOT_B6P4_Z8', '04_NOT_B64_Z8')


FAULTS += [
    Fault('v_y04_1', 'Machine bed entered as 2500x1220 instead of the router\'s 2440x1220',
          'Sheets are split and nested for a 2500 mm bed: the dealer saws 2500 mm pieces and parts placed in the last 60 mm along X are beyond the ShopBot travel and cannot be cut or clamped.',
          params=_v_y04_1, source='variant of y04: only the long axis wrong, smaller magnitude'),
    Fault('v_y04_2', 'Machine bed entered as 2440x1250 instead of the router\'s 2440x1220',
          'The nest uses 30 mm more in Y than the router can reach: pieces are sawn 1250 wide and the parts along the far edge are outside the machine envelope.',
          params=_v_y04_2, source='variant of y04: only the short axis wrong'),
    Fault('v_y04_3', 'Machine bed entered as the full chipboard format 2800x2070 instead of 2440x1220',
          'Nothing is split by the dealer: whole 2800x2070 sheets are nested as if they fit the ShopBot, so a large share of every sheet lies outside the bed and the sheet cannot even be laid on the machine.',
          params=_v_y04_3, source='variant of y04: material format copied into the machine-envelope field'),
    Fault('v_y23_1', 'DXF: decimal marker lost in the HDF contour depth (Z5P9 -> Z59)',
          'CAM reads a 59 mm cut depth for the 5.9 mm drawer-bottom sheet: the bit plunges through the HDF and deep into the spoilboard/table, breaking the bit.',
          dxf=_v_y23_1, source='variant of y23: same corruption on a different material/sheet'),
    Fault('v_y23_2', 'DXF: decimal marker shifted in contour-layer depth (Z18P8 -> Z1P88)',
          'CAM reads a 1.88 mm cut depth: the contours only scribe the surface, no part is cut free and the whole sheet has to be re-run or sawn by hand.',
          dxf=_v_y23_2, source='variant of y23: decimal misplaced instead of dropped (too shallow instead of too deep)'),
    Fault('v_y23_3', 'DXF: decimal marker lost in the groove-layer width (04_NOT_B6P4 -> B64)',
          'CAM reads 64 mm wide bottom grooves on 120 mm drawer sides and ends: the pockets eat half of every part, cross the confirmat holes and the drawer parts are scrap.',
          dxf=_v_y23_3, source='variant of y23: layer-name decimal lost in a width field of another layer'),
]


# ------------------------------------------------------------------ variants of v_y23_3 (decimal marker lost in a size field of a non-contour layer)
def _v_v_y23_3_1(files):
    k = [f for f in sorted(files) if '04_NOT_B6P4_Z8' in files[f]][-1]   # the second groove sheet (plate4), not plate3
    files[k] = files[k].replace('04_NOT_B6P4_Z8', '04_NOT_B0P64_Z8')


def _v_v_y23_3_2(files):
    k = _v_sheet_with(files, r'^01_BOR_D3P17_Z10$')
    files[k] = files[k].replace('01_BOR_D3P17_Z10', '01_BOR_D317_Z10')


def _v_v_y23_3_3(files):
    k = _v_sheet_with(files, r'^01_BOR_D4P5_Z3$')
    files[k] = files[k].replace('01_BOR_D4P5_Z3', '01_BOR_D45_Z3')


FAULTS += [
    Fault('v_v_y23_3_1', 'DXF: decimal marker shifted in the groove-layer width on the second groove sheet (B6P4 -> B0P64)',
          'CAM reads a 0.64 mm wide groove: the drawer sides/ends on that sheet get only a hairline scratch instead of a 6.4 mm groove, the drawer bottom cannot be slid in and every drawer from that sheet cannot be assembled.',
          dxf=_v_v_y23_3_1, source='variant of v_y23_3: other sheet, decimal shifted (too narrow instead of too wide)'),
    Fault('v_v_y23_3_2', 'DXF: decimal marker lost in the slide pilot-hole diameter on the oak sheet (D3P17 -> D317)',
          'CAM reads a 317 mm diameter, 10 mm deep bore for every slide pilot: the router pockets huge circles through the inside faces of the oak parts, which are scrap.',
          dxf=_v_v_y23_3_2, source='variant of v_y23_3: same corruption in a drill-diameter field on a different layer/sheet'),
    Fault('v_v_y23_3_3', 'DXF: decimal marker lost in the plinth-screw hole diameter (D4P5 -> D45)',
          'CAM reads 45 mm holes where the 4.5 mm plinth-strip screw holes go in the carcass bottom: large craters are machined into the bottom panel, the screws have nothing to bite against and the panel is scrap.',
          dxf=_v_v_y23_3_3, source='variant of v_y23_3: decimal lost in a smaller diameter field, different part'),
]


# ------------------------------------------------------------------ variants of h4_01 (dealer saw kerf entered wrong)
def _v_h4_01_1(P, S):
    P['plater']['sagsnitt'] = 0.4                  # decimal slip: 4 mm typed as 0.4


def _v_h4_01_2(P, S):
    P['plater']['sagsnitt'] = 2                    # half-kerf (per-side offset) entered instead of the full ~4 mm kerf


def _v_h4_01_3(P, S):
    P['plater']['sagsnitt'] = 1                    # thin track-saw blade figure instead of the panel saw's ~4 mm


# ------------------------------------------------------------------ variants of h4_06 (dimension typed with wrong magnitude)
def _v_h4_06_1(P, S):
    P['ytre']['topp_overheng_front'] = 121         # extra digit: 21 -> 121


def _v_h4_06_2(P, S):
    P['ytre']['topp_overheng_front'] = P['ytre']['topp_overheng_front'] * 100   # two decimals lost: 21 -> 2100


def _v_h4_06_3(P, S):
    P['ytre']['dybde_korpus'] = P['ytre']['dybde_korpus'] * 10                  # carcass depth 430 -> 4300


# ------------------------------------------------------------------ variants of h4_17 (groove depth does not match the bottom size)
def _v_h4_17_1(parts, asm, info):
    for p in parts:
        if p['code'] in ('S', 'SH'):
            for o in p['ops']:
                if o['kind'] == 'groove':
                    o['z'] = round(o['z'] / 2, 2)


def _v_h4_17_2(parts, asm, info):
    for p in parts:
        if p['code'] == 'E2':
            for o in p['ops']:
                if o['kind'] == 'groove':
                    o['z'] = round(o['z'] * 0.75, 2)


def _v_h4_17_3(parts, asm, info):
    for p in parts:
        if p['code'] == 'SB':
            p['L'] = round(p['L'] + 2 * info['nd'], 2)
            p['B'] = round(p['B'] + 2 * info['nd'], 2)


FAULTS += [
    Fault('v_h4_01_1', 'Dealer saw kerf entered as 0.4 mm instead of 4 mm (plater.sagsnitt)',
          'The offcut pieces are nested 3.6 mm larger than the panel saw leaves them: parts placed along the far edge of the 356/846 mm offcuts run off the real board and are ruined.',
          params=_v_h4_01_1, source='variant of h4_01: decimal slip instead of zero, smaller magnitude'),
    Fault('v_h4_01_2', 'Dealer saw kerf entered as 2 mm (half the blade, a per-side offset) instead of ~4 mm',
          'Each offcut piece is planned 2 mm larger than what the panel saw leaves: parts nested tight against the far edge of the 356/846 mm offcuts lose their edge or run off the board.',
          params=_v_h4_01_2, source='variant of h4_01: half-kerf confusion, smallest magnitude'),
    Fault('v_h4_01_3', 'Dealer saw kerf entered as 1 mm (thin track-saw figure, not the panel saw)',
          'The panel saw removes ~4 mm: the offcuts are planned 3 mm too large and the contours at their far edge run off the real piece.',
          params=_v_h4_01_3, source='variant of h4_01: plausible-looking but understated kerf'),
    Fault('v_h4_06_1', 'Top front overhang typed 121 instead of 21 (extra digit)',
          'The top sticks out 121 mm past the carcass, ~100 mm in front of the drawer fronts: unsupported lip that tips the chest forward when leaned on, and the big oak top is wrong.',
          params=_v_h4_06_1, source='variant of h4_06: extra-digit typo, smaller magnitude'),
    Fault('v_h4_06_2', 'Top front overhang typed 100x too large (2100 instead of 21)',
          'The top becomes ~2.5 m deep - it cannot be cut on the machine, and any such top would tip the chest over immediately.',
          params=_v_h4_06_2, source='variant of h4_06: two decimals lost'),
    Fault('v_h4_06_3', 'Carcass depth typed 10x too large (4300 instead of 430)',
          'Sides, top, bottom and middle wall become 4.3 m deep: they do not fit the router or the sheets, and the drawers/slides no longer match the carcass.',
          params=_v_h4_06_3, source='variant of h4_06: same 10x slip in another overall dimension'),
    Fault('v_h4_17_1', 'Generator bug: grooves in the drawer sides half as deep as the bottom is sized for',
          'The bottom is sized for full-depth grooves in S/SH, but they are only half as deep: the bottom bottoms out in the side grooves and the ends cannot be pulled tight to the sides - box joints gape by several mm.',
          parts=_v_h4_17_1, source='variant of h4_17: same mistake on the other drawer parts (sides)'),
    Fault('v_h4_17_2', 'Generator bug: groove in the back drawer end only 3/4 as deep as the bottom is sized for',
          'The bottom runs 2 mm too deep into the back end: the back end cannot seat against the sides, the box is out of square and confirmats pull the joint open.',
          parts=_v_h4_17_2, source='variant of h4_17: smaller magnitude, back end only'),
    Fault('v_h4_17_3', 'Generator bug: drawer bottom sized for grooves twice as deep as cut',
          'The HDF bottom is cut 16 mm too long and too wide for the 8 mm grooves: it cannot be slid in and the drawer boxes cannot be closed - all bottoms recut.',
          parts=_v_h4_17_3, source='variant of h4_17: mismatch from the bottom side instead of the groove side'),
]
