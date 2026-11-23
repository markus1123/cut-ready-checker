"""Training faults: the rule writer may read these. Each is one realistic way a cut goes wrong."""
from fc.core import Fault
from faults.helpers import part, first_dxf, drop_first_circle, shift_first_part


def _set(path, val):
    def f(P, S):
        d = P
        for k in path[:-1]:
            d = d[k]
        d[path[-1]] = val
    return f


def _slide(key, val):
    def f(P, S):
        S[key] = val
    return f


def _dxf_re(pat, new):
    import re

    def f(files):
        for k in files:
            files[k] = re.sub(pat, new, files[k])
    return f


def _dxf_all(old, new):
    def f(files):
        for k in files:
            files[k] = files[k].replace(old, new)
    return f


FAULTS = [
    Fault('t01', 'Slide clearance entered as 12.7 - 0.3 (box 0.6 mm too wide)',
          'Ball-bearing slides need >= 12.7 mm per side; 12.4 mm binds or will not engage.',
          params=_slide('sideklaring_tillegg', -0.3)),
    Fault('t02', 'Handle c/c 790 on an 800 mm front',
          'Handle holes 5 mm from the edge; melamine blows out.', params=_set(['front', 'handtak_cc'], 790)),
    Fault('t03', '3 mm hardboard as bottom of an 800 mm wide drawer',
          'Bottom sags/pops out of the groove under 10-15 kg of clothes.',
          params=lambda P, S: P['tykkelse_malt'].update(skuffebunn=3.0)),
    Fault('t04', 'Bottom groove 12 mm deep in an 18.8 mm drawer side',
          'Side breaks along the groove.', params=_set(['skuff', 'not_dybde'], 12)),
    Fault('t05', 'Generator bug: drawer ends E1/E2 1 mm too long',
          'Box 1 mm wider than the slides allow: 12.5 mm per side, drawer binds.',
          parts=lambda parts, asm, info: [p.update(L=p['L'] + 1) for p in parts if p['code'] in ('E1', 'E2')]),
    Fault('t06', 'DXF: contour depth set to 18.5 on 18.8 mm boards',
          'Parts are not cut through; prying them out chips the melamine.',
          dxf=_dxf_all('10_KONTUR_UTVENDIG_Z18P8', '10_KONTUR_UTVENDIG_Z18P5')),
    Fault('t07', 'DXF export dropped one Minifix-bolt hole',
          'One joint has no bolt; found during assembly, part must be re-drilled by hand.',
          dxf=lambda files: files.__setitem__(first_dxf(files, 'eik'), drop_first_circle(files[first_dxf(files, 'eik')], '01_BOR_D5_Z11'))),
    Fault('t08', 'DXF: one part moved 30 mm into its neighbour',
          'Two parts overlap; the router cuts through both.',
          dxf=lambda files: files.__setitem__(first_dxf(files, 'hvit-19_2440x1220'), shift_first_part(files[first_dxf(files, 'hvit-19_2440x1220')], 0, 30))),
    Fault('t09', 'DXF: one part moved 400 mm, off the sheet',
          'The part is cut in air/spoilboard; a whole sheet wasted.',
          dxf=lambda files: files.__setitem__(first_dxf(files, 'eik-dew-19_2440x1220'), shift_first_part(files[first_dxf(files, 'eik-dew-19_2440x1220')], 400, 0))),
    Fault('t10', 'Gap between nested parts 4 mm with a 6.35 mm bit',
          'Neighbouring cuts merge; parts lose their edge and come loose mid-cut.',
          params=_set(['verksted', 'avstand_mellom_deler'], 4)),
    Fault('t11', 'Confirmat 5 mm from top edge of drawer side',
          'Screw splits the side.', params=_set(['skuff', 'konfirmat_y'], [28, -5])),
    Fault('t12', 'Gap between fronts 0 mm',
          'Fronts rub and chip each other.', params=_set(['front', 'fuge'], 0)),
    Fault('t13', 'Handle screws M4x30 through 37.6 mm',
          'Screw does not reach the handle thread.', params=_set(['front', 'handtak_skrue_lengde'], 30)),
    Fault('t15', 'Generator bug: bottom groove on E1 2 mm higher than on sides',
          'Bottom cannot enter all four grooves; box will not close square.',
          parts=lambda parts, asm, info: [o.update(y1=o['y1'] + 2, y2=o['y2'] + 2) for o in part(parts, 'E1')['ops'] if o['kind'] == 'groove']),
    Fault('t16', 'Generator bug: Minifix bolt holes in the top forget the overhang',
          'Bolts land 21 mm off the side edge holes; top cannot be fitted.',
          parts=lambda parts, asm, info: [o.update(y=o['y'] - 21) for o in part(parts, 'A')['ops'] if 'Minifix' in o['note']]),
    Fault('t17', 'Generator bug: side bolt hole for the bottom at y = T instead of T/2',
          'Bolt misses the edge hole in the bottom by 9 mm.',
          parts=lambda parts, asm, info: [o.update(y=o['y'] * 2) for o in part(parts, 'C')['ops'] if o['note'] == 'Minifix-bolt mot bunn']),
    Fault('t19', 'Plinth strip only 45 mm wide, 1400 mm long',
          'Narrow long part shifts under vacuum/hold-down and is ruined.', params=_set(['korpus', 'bunnlist_hoyde'], 45)),
    Fault('t24', 'Fronts flush to the bottom (edge 0) -> bottom drawer 1 mm above the carcass bottom',
          'Bottom drawer scrapes.', params=_set(['front', 'kant_topp_bunn'], 0)),
    Fault('t25', '450 mm slide in a 430 mm carcass', 'Slide does not fit.', params=_slide('lengde', 450)),
    Fault('t26', 'Fronts banded with 2 mm ABS (cut sizes not reduced)',
          'Gap between fronts goes from 3 mm to -1 mm; fronts collide.',
          params=_set(['front', 'kantlist_tykkelse'], 2.0)),
    Fault('t29', 'DXF: Minifix housing pocket depth 18.8 (through the board)',
          'Housing goes through the visible face.', dxf=_dxf_re(r'03_LOMME_D15_Z[0-9P]+', '03_LOMME_D15_Z18P8')),
    Fault('t30', 'DXF header says inches',
          'VCarve imports the job 25.4x too big (or the operator rescales by guess).', dxf=_dxf_all('$INSUNITS\n70\n4', '$INSUNITS\n70\n1')),
    Fault('t32', 'Generator bug: drawer bottom 4 mm too wide',
          'Bottom bottoms out in the groove; box cannot be closed.',
          parts=lambda parts, asm, info: part(parts, 'SB').update(L=part(parts, 'SB')['L'] + 4)),
    Fault('t33', 'Regression: right side cut as an identical copy of the left (the bug found on 2026-11-22)',
          'Right side: band on the back edge, slide holes 30+ mm too far back; drawer cannot close square.',
          parts=lambda parts, asm, info: part(parts, 'CH').update(ops=[dict(o) for o in part(parts, 'C')['ops']], bands=part(parts, 'C')['bands']),
          source='found by R04 on the real kommode'),
    Fault('t34', 'Regression: right drawer sides identical to left',
          '8 right drawer sides get slide holes front<->back; slides cannot be mounted.',
          parts=lambda parts, asm, info: part(parts, 'SH').update(ops=[dict(o) for o in part(parts, 'S')['ops']]),
          source='found by R04 on the real kommode'),

    # --- from manufacturer manuals (docs/rules-from-manuals.md), 2026-11-22
    Fault('t35', 'Minifix housing depth for 18 mm board drilled in 19 mm board (13.5)',
          'Cam sits 0.5 mm proud; bolt head misses the ramp, joint does not pull tight.',
          params=_set(['korpus', 'minifix_hus_dybde'], 13.5), source='Häfele TCH 2023 p 7.13'),
    Fault('t36', 'Minifix edge bore only 20 mm deep with B24 housing',
          'Bolt head stops short of the cam; joint cannot be closed.',
          params=_set(['korpus', 'minifix_kanthull_dybde'], 20), source='Häfele TCH 2023 p 7.13/7.18'),
    Fault('t37', 'Groove feed 3000 mm/min with 5.6 mm hardboard (groove cut with the 1/8" bit)',
          'Above Amana chipload for 1/8"; bit snaps mid-job or burns the groove.',
          params=lambda P, S: (P['maskintid'].update(mating_not=3000), P['tykkelse_malt'].update(skuffebunn=5.6)),
          source='Amana compression spiral sheet v12'),
    Fault('t38', 'Contour feed 6000 mm/min at 9.5 mm per pass',
          'Over Amana 1/4" limit for 1.5xD passes; chipped melamine, deflection, broken bit.',
          params=lambda P, S: P['maskintid'].update(mating_kontur=6000), source='Amana compression spiral sheet v12'),
    Fault('t39', 'Slide holes typed in from another length (KA 4532/400 with 37/165/357)',
          'Rear screw misses the runner hole; runner sits crooked.',
          params=_slide('korpus_hull', [[37, 0], [165, 0], [357, 0]]), source='Hettich MS 10547 p2'),
    Fault('t40', '1 mm ABS banding on the fronts, cut sizes not reduced',
          'Fronts grow 2 mm each way; the 3 mm gap closes to 1 mm and fronts rub.',
          params=_set(['front', 'kantlist_tykkelse'], 1.0), source='Microvellum KB, cut size = finished - band'),
    Fault('t41', 'Onion skin 1.5 mm',
          'Parts do not separate; tearing them out chips the melamine face.',
          params=lambda P, S: P['verksted'].update(holdning='onion', onion_skin=1.5), source='ShopBot hold-down guide p8'),
    Fault('t42', 'Vacuum table only, small drawer parts without tabs',
          'Small parts move in the last pass and get gouged.',
          params=lambda P, S: (P['verksted'].update(holdning='vakuum'), P.update(kolonner=3)), source='ShopBot hold-down guide p7'),
    Fault('t43', 'Slide screws Ø4x10',
          'Only 8.8 mm in chipboard; runner pulls out under load.',
          params=_slide('skrue_lengde', 10), source='Hettich MS 10547 p1'),
]
