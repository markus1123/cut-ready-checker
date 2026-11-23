"""R40 fastener grip: every screw / bolt in the chest can actually be installed and clamp what it is meant to clamp.

A threaded fastener that crosses a joint needs a chain of holes that fits it. The rule follows each fastener
in the 3D model (fc.world) and checks the four ways that chain fails, whatever the part or the hardware:

(a) bite vs passage: where two threaded-hardware bores of the same family meet coaxially across a joint
    (Minifix bolt: face hole + edge hole; confirmat: clearance + pilot; plinth screw: clearance + pilot), the
    hole the thread bites into must be at most 0.8 x the hole the shank passes through. Manufacturer data:
    Häfele Minifix bolt Ø5 bite / Ø8 edge bore (0.63), Häfele confirmat 7x50 Ø5 pilot / Ø7 clearance (0.71),
    4 mm wood screw Ø3 pilot / Ø4.5 clearance (0.67). Equal holes mean either the thread has nothing to cut
    into (joint cannot be tightened) or the shank cannot pass.
(b) pull-through: a clearance hole must be at most 0.75 x the diameter that bears on the board around it:
    the countersink written in the note ("senk Ø10"), else a washer ("skive": DIN 9021 OD = 3 x d), else a
    screw head (DIN 7505 / ISO 7049 head ≈ 2 x d). Below a ~1/8-of-diameter bearing ring on each side the
    head/washer crushes the chipboard edge and pulls through (workshop practice; adjustable front fixings
    are Ø8-Ø9 for 4 mm screws with 12 mm washers: Blum/Hettich front-fixing instructions).
(c) landing: a screw "d x L" driven through a part must come out into another part of the assembly over the
    part of its length that sticks out (sampled at 1 mm and at the tip). A screw that ends in air holds nothing
    (holes on the wrong part, wrong face, wrong end).
(d) patterns: hardware drilled at a centre distance ("c/c N": bar handles, two-bolt fittings) needs its holes
    in complete pairs N ± 0.5 mm apart on every part; a lone hole cannot take the fitting.
"""
import math, re
from fc.core import rule, Finding
from fc.world import frames, holes, add, mul, dot, inside
from fc.geom import seg_dist

BITE_MAX = 0.8          # bite hole / passage hole, see (a)
BEAR_MAX = 0.75         # clearance hole / bearing diameter, see (b)
THREADED = (('minifix-bolt', 'minifix-bolt'), ('konfirmat', 'konfirmat'), ('skrue', 'skrue'),
            ('forbor skrue', 'skrue'), ('bolt', 'bolt'))
SIZE = re.compile(r'(\d+(?:[.,]\d+)?)\s*x\s*(\d+(?:[.,]\d+)?)')
CSK = re.compile(r'senk\s*Ø\s*(\d+(?:[.,]\d+)?)', re.I)
CC = re.compile(r'c/c\s*(\d+(?:[.,]\d+)?)', re.I)


def _num(s):
    return float(s.replace(',', '.'))


def _family(note):
    n = note.lower()
    return next((f for p, f in THREADED if n.startswith(p)), None)


def _seg(h):
    return h['entry'], add(h['entry'], mul(h['dir'], h['depth'] if isinstance(h['depth'], (int, float)) else 0))


def _bores(F):
    """One axis segment per drilled op per instance (a through hole is listed once, from its op face)."""
    out = []
    for f in F:
        for h in holes(f):
            o = h['op']
            if o['kind'] == 'through' and h['end'] != o['face']:
                continue
            if not isinstance(h['depth'], (int, float)):
                continue
            out.append((f, h))
    return out


def bite_vs_passage(F):
    B = [(f, h, _seg(h)) for f, h in _bores(F) if _family(h['op']['note'])]
    out, seen = [], set()
    for i, (f, h, (p1, q1)) in enumerate(B):
        fa = _family(h['op']['note'])
        for f2, h2, (p2, q2) in B[i + 1:]:
            if f2 is f or _family(h2['op']['note']) != fa:
                continue
            if abs(dot(h['dir'], h2['dir'])) < 0.999:
                continue
            if seg_dist(p1, q1, p2, q2) > 0.5:
                continue
            # perpendicular offset between the two axes
            r = [a - b for a, b in zip(p2, p1)]
            along = dot(r, h['dir'])
            off = math.sqrt(max(0.0, dot(r, r) - along * along))
            if off > 0.5:
                continue
            small, big = sorted((h['d'], h2['d']))
            if small > BITE_MAX * big + 1e-6:
                key = (f['code'], f2['code'], h['op']['note'], h2['op']['note'], h['d'], h2['d'])
                if key in seen:
                    continue
                seen.add(key)
                out.append(Finding('R40', 'error',
                    '%s "%s" Ø%g meets %s "%s" Ø%g on one axis: the hole the thread bites into must be <= %.0f %% of the '
                    'hole the shank passes (Häfele: Minifix Ø5/Ø8, confirmat Ø5/Ø7); the joint cannot be tightened.'
                    % (f['code'], h['op']['note'][:30], h['d'], f2['code'], h2['op']['note'][:30], h2['d'], 100 * BITE_MAX),
                    f['code']))
    return out


def pull_through(parts):
    out = []
    for p in parts:
        seen = set()
        for o in p['ops']:
            if o['kind'] != 'through' or not isinstance(o.get('d'), (int, float)):
                continue
            note = o['note']
            m, c = SIZE.search(note), CSK.search(note)
            if c:
                bear, what = _num(c.group(1)), 'countersink Ø%s' % c.group(1)
            elif m and 'skive' in note.lower():
                bear, what = 3 * _num(m.group(1)), 'DIN 9021 washer Ø%g' % (3 * _num(m.group(1)))
            elif m and _family(note):
                bear, what = 2 * _num(m.group(1)), 'screw head Ø%g' % (2 * _num(m.group(1)))
            else:
                continue
            if o['d'] > BEAR_MAX * bear + 1e-6 and (o['d'], note) not in seen:
                seen.add((o['d'], note))
                out.append(Finding('R40', 'error', '%s: Ø%g clearance hole for "%s" under a %s (max Ø%.1f); the head pulls through the board.'
                                   % (p['code'], o['d'], note[:40], what, BEAR_MAX * bear), p['code']))
    return out


def landing(d, F):
    boxes = [a['b'] for a in d.asm]
    out, seen = [], set()
    for f, h in _bores(F):
        o = h['op']
        if o['kind'] != 'through':
            continue
        m = SIZE.search(o['note'])
        if not m or not _family(o['note']):
            continue
        L, t = _num(m.group(2)), f['part']['t']
        exit_ = add(h['entry'], mul(h['dir'], t))
        stick = L - t
        key = (f['code'], o['note'])
        bad = stick <= 0.5
        if not bad:
            for s in (1.0, stick - 0.5):
                pt = add(exit_, mul(h['dir'], s))
                if not any(inside(b, pt) for b in boxes if list(b) != list(f['box'])):
                    bad = True
                    break
        if bad and key not in seen:
            seen.add(key)
            out.append(Finding('R40', 'error', '%s (%s): the %s screw through "%s" comes out into empty space; it fastens nothing.'
                               % (f['code'], f['label'], m.group(0), o['note'][:40]), f['code']))
    return out


def patterns(parts):
    out = []
    for p in parts:
        groups = {}
        for o in p['ops']:
            m = CC.search(o['note'])
            if m and 'x' in o and o['kind'] != 'manual':
                groups.setdefault((o['note'], _num(m.group(1))), []).append(o)
        for (note, cc), hs in groups.items():
            lone = [a for a in hs if not any(b is not a and abs(math.hypot(a['x'] - b['x'], a['y'] - b['y']) - cc) <= 0.5 for b in hs)]
            if lone or len(hs) % 2:
                out.append(Finding('R40', 'error', '%s: %d hole(s) for "%s" without a partner %g mm away; the fitting cannot be mounted.'
                                   % (p['code'], max(len(lone), 1), note[:40], cc), p['code']))
    return out


@rule('R40', 'Every screw/bolt can grip: bite hole < 0.8 x passage, clearance < 0.75 x head/washer, screw lands in a part, c/c hardware in full pairs')
def fastener_grip(d):
    F = frames(d)
    return bite_vs_passage(F) + pull_through(d.parts) + landing(d, F) + patterns(d.parts)
