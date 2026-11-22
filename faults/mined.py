"""Mined faults: failure modes taken from hardware instructions, workshop practice and CNC forums.
Each one changes the generated output and is a real defect the workshop would hit."""
from fc.core import Fault
from faults.helpers import part


def _set(path, val):
    def f(P, S):
        d = P
        for k in path[:-1]:
            d = d[k]
        d[path[-1]] = val
    return f


def _grain_off(P, S):
    # Catalogue entry for the oak decor copied from a plain white board: retning=false -> nester may rotate parts.
    for m in P['_valg'].values():
        if m['id'] == 'fritzoe-kaindl-eik-dew-19':
            m['retning'] = False


def _slide_inset_ref(P, S):
    # Hole pattern taken from the slide drawing for INSET fronts (measured from the front face of the drawer front,
    # i.e. 19 mm front thickness added), used on an OVERLAY kommode.
    S['korpus_hull'] = [[x + 19, y] for x, y in S['korpus_hull']]
    S['korpus_hull_alternativ'] = [[x + 19, y] for x, y in S['korpus_hull_alternativ']]


def _band_joint_edge(parts, asm, info):
    # Band list edited by hand: the sides also get ABS on the top edge, where the top sits on them with Minifix/dowels.
    for code in ('C', 'CH'):
        p = part(parts, code)
        p['bands'] = p['bands'] + ['overkant (y=B)']


FAULTS = [
    Fault('m01', 'Minifix housing 34 mm from the edge with B24 bolts (24 mm system)',
          'Minifix 15 comes in drilling distance B24 and B34; the bolt length is matched to the distance. With the '
          'housing 10 mm further in than the bolt reaches, the cam turns past the bolt head and the joint never pulls '
          'tight (or the operator over-tightens and cracks the chipboard).',
          params=_set(['korpus', 'minifix_hus_avstand'], 34),
          source='Häfele Minifix 15 catalogue / drilling template: housing distance B24 vs B34 must match the bolt type'),
    Fault('m02', 'Dowel holes 12 mm (face) + 15 mm (edge) = 27 mm for 8x35 dowels',
          'Hole depths must add up to dowel length + ~2 mm glue/air space. With 27 mm the 8x30/8x35 dowel bottoms out '
          'and the carcass joint stays open 5-8 mm; Minifix cannot close it either and the edge splits.',
          params=_set(['korpus', 'plugg_dybde_kant'], 15),
          source='Dowel joint practice (Häfele/Würth dowel tables, Festool/Wolfcraft dowel jig manuals): '
                 'face depth + edge depth = dowel length + 1-2 mm; 8 mm dowel in 19 mm board: ~12 face / ~22-25 edge'),
    Fault('m03', 'Oak decor board marked "no grain direction" -> nester rotates parts 90°',
          'Kaindl oak decor has a printed grain. With rotation allowed the nester turns one side panel 90° on the sheet '
          '(653x430 instead of 430x653): the two visible sides get grain in different directions and one must be '
          're-cut from a new oak sheet.',
          params=_grain_off,
          source='Woodworking/nesting practice (VCarve/Cutlist "grain direction lock", panel-saw cutting lists): '
                 'decor and veneer boards must keep grain orientation'),
    Fault('m04', 'Slide screws 20 mm long into 18.8 mm carcass sides',
          'Screw goes 18.8 mm into an 18.8 mm side: the tip lifts or pierces the finished OUTER face of the oak side '
          '(visible). Hettich/Blum specify 3.5x15/16 chipboard or 6.3x13 Euro screws for side mount slides in 16-19 mm.',
          params=lambda P, S: S.update(skrue_lengde=20),
          source='Hettich KA 4532 / Blum mounting instructions: screw length for side-mount slides in 16-19 mm panels; '
                 'common forum failure "screw came through the side of the cabinet"'),
    Fault('m05', 'Slide hole pattern from the INSET drawing (+19 mm) on an overlay kommode',
          'Cabinet member sits 19 mm further back while the drawer member is unchanged: the closed position is 19 mm '
          'deeper than the carcass front, so the overlay front hits the carcass edge 19 mm before the slide reaches its '
          'stop. Self/soft-close never engages and the drawer springs open.',
          params=_slide_inset_ref,
          source='Hettich/Blum slide mounting instructions give separate setback dimensions for overlay vs inset fronts '
                 '(inset: add front thickness); mixing them is a common cabinet-maker error'),
    Fault('m06', 'Edge band added on the top edge of the sides (joint edge) without shortening the part',
          'The top sits on the banded edge: sides become 1-2 mm taller than the middle wall, top rocks/gaps, '
          'and the Minifix/dowel edge holes are drilled through ABS which chips and misaligns.',
          parts=_band_joint_edge,
          source='Edge-banding practice (Homag/Biesse banding guides, cutlist rules): never band edges that are joined; '
                 'if you must, deduct band thickness from the cut size'),
]
