"""Variants of practice faults written by the loop variant agent (blind to the rule under test)."""
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
