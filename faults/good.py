"""Known-good variants. Any error on these is a false alarm (the rule is wrong or too strict)."""
from fc.core import Fault


def _p(fn):
    return fn


def _three_cols(P, S):
    P['ytre']['bredde'] = 1800; P['kolonner'] = 3


def _one_col(P, S):
    P['ytre']['bredde'] = 820; P['kolonner'] = 1; P['skuff']['hoyde'] = 100; P['skuff']['front_skrue_y'] = [35, 70]


def _skuff16(P, S):
    P['tykkelse_malt']['skuff'] = 15.8; P['tykkelse_nominell']['skuff'] = 16.0; P['skuff']['not_dybde'] = 7


def _thin(P, S):
    P['tykkelse_malt'].update(korpus=18.4, front=18.4, skuff=18.4, skuffebunn=5.6)


def _deep(P, S):
    P['ytre']['dybde_korpus'] = 500
    S.update(lengde=450, min_innvendig_dybde=454,
             korpus_hull=[[37, 0], [261, 0], [421, 0]], korpus_hull_alternativ=[[69, 0], [293, 0], [389, 0]],
             skuff_hull=[[35, 0], [259, 0]])


def _gaps(P, S):
    P['front']['kant_sider'] = 2; P['front']['fuge'] = 4


FAULTS = [
    Fault('g01', 'Nominal design, ready state', good=True),
    Fault('g02', '3 columns, 1800 wide', params=_three_cols, good=True),
    Fault('g03', '1 column, 820 wide, 100 mm boxes', params=_one_col, good=True),
    Fault('g04', '16 mm drawer boxes', params=_skuff16, good=True),
    Fault('g05', 'Thin boards measured (18.4 / 5.6)', params=_thin, good=True),
    Fault('g06', '500 deep with 450 slides', params=_deep, good=True),
    Fault('g07', 'Side edge 2 mm, front gap 4 mm', params=_gaps, good=True),
]
