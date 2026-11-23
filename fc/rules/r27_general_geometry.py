"""General geometry rules: instead of one rule per known mistake, check whole classes of failure in the 3D model.

R27 bores: two drilled features from different hardware families must not meet. Within one board they need
    >= 4 mm of board between them (chipboard crumbles below that; good designs here have >= 6.6 mm). Across boards
    they must not intersect at all (a screw running into a handle bolt). Families that are designed to meet
    (Minifix bolt + housing, dowel + dowel, confirmat + pilot, plinth screw + its pilot) are exempt.
R28 interference: no two parts or hardware items (legs, slides) may occupy the same space, except a drawer
    bottom sitting in its groove.
R29 slides level: for every drawer, the slide screw holes on both drawer sides and on both cabinet walls of
    its opening are at one height (tolerance 0.5 mm, Hettich: both runners in one plane).
R30 completeness: every part's quantity equals the number of places it is used in the 3D assembly.
R31 groove wall: the board left between a groove and the nearest edge is at least as wide as the groove.
"""
from collections import Counter
from fc.core import rule, Finding
from fc.world import frames, holes, add, mul
from fc.geom import seg_dist, box_overlap
import nestlib

FAM = [('Minifix', 'minifix'), ('Plugg', 'plugg'), ('Konfirmat', 'konfirmat'), ('Skrue til list', 'list'),
       ('Forbor skrue', 'list'), ('Håndtak', 'handle'), ('Skinne', 'slide')]
MEET_OK = {'minifix', 'plugg', 'konfirmat', 'list', 'handle'}   # same family may meet (that is the joint)
MIN_WEB = 4.0


def fam(note):
    return next((f for p, f in FAM if note.startswith(p)), note.split(' ')[0])


def seg(h):
    return h['entry'], add(h['entry'], mul(h['dir'], h['depth']))


@rule('R27', 'Drilled features of different hardware never meet: >= 4 mm of board between them in one part, no intersection across parts')
def bores(d):
    H = [(f, h) for f in frames(d) for h in holes(f)]
    out, seen = [], set()
    for i, (f, h) in enumerate(H):
        a = fam(h['op']['note'])
        p1, q1 = seg(h)
        for f2, h2 in H[i + 1:]:
            if f is f2 and h['op'] is h2['op']:
                continue
            b = fam(h2['op']['note'])
            if a == b and a in MEET_OK:
                continue
            web = seg_dist(p1, q1, *seg(h2)) - h['d'] / 2 - h2['d'] / 2
            same = f is f2
            if (same and web < MIN_WEB) or (not same and web < 0):
                key = (f['code'], h['op']['note'], f2['code'], h2['op']['note'])
                if key in seen:
                    continue
                seen.add(key)
                where = 'in %s' % f['code'] if same else 'between %s and %s' % (f['code'], f2['code'])
                out.append(Finding('R27', 'error', '%s "%s" and "%s": %s (need %s).'
                                   % (where, h['op']['note'][:40], h2['op']['note'][:40],
                                      '%.1f mm of board between them' % web if web >= 0 else 'they run into each other',
                                      '>= %g mm' % MIN_WEB if same else 'no contact'), f['code']))
    return out


@rule('R28', 'No two parts or hardware items occupy the same space in the assembled chest (drawer bottoms in their grooves excepted)')
def interference(d):
    A, out, seen = d.asm, [], set()
    groove = d.P['skuff']['not_dybde'] + 0.6
    for i, a in enumerate(A):
        for b in A[i + 1:]:
            o = box_overlap(a['b'], b['b'])
            if min(o) <= 0.3:
                continue
            pair = {a['code'], b['code']}
            if 'SB' in pair and pair & {'S', 'SH', 'E1', 'E2'} and sorted(o)[0] <= groove:
                continue
            key = tuple(sorted((a['code'], b['code'])))
            if key in seen:
                continue
            seen.add(key)
            out.append(Finding('R28', 'error', '%s and %s overlap by %.1f mm in the assembled chest.'
                               % (a['label'], b['label'], min(o)), a['code']))
    return out


@rule('R29', 'Each drawer\'s slide holes are at one height on both drawer sides and both cabinet walls (<= 0.5 mm)')
def slides_level(d):
    F = frames(d)
    lab = {f['label']: f for f in F}
    walls = [(f, h) for f in F if f['code'] in ('C', 'CH', 'D') for h in holes(f) if 'Skinne' in h['op']['note']]
    out = []
    for f in F:
        if f['code'] != 'S':
            continue
        tag = f['label'].split(' ', 1)[1]
        sh = lab.get('SH ' + tag)
        if not sh:
            continue
        x0, x1 = f['box'][0], sh['box'][0] + sh['box'][3]
        z0, z1 = f['box'][2], f['box'][2] + f['box'][5]
        zz = lambda fr: {round(h['entry'][2], 1) for h in holes(fr) if 'Skinne' in h['op']['note']}
        left_w = {round(h['entry'][2], 1) for g, h in walls if x0 - 20 <= h['entry'][0] <= x0 + 0.1 and z0 - 40 <= h['entry'][2] <= z1 + 40}
        right_w = {round(h['entry'][2], 1) for g, h in walls if x1 - 0.1 <= h['entry'][0] <= x1 + 20 and z0 - 40 <= h['entry'][2] <= z1 + 40}
        groups = {'left drawer side': zz(f), 'right drawer side': zz(sh), 'left cabinet wall': left_w, 'right cabinet wall': right_w}
        groups = {k: v for k, v in groups.items() if v}
        if len(groups) < 2:
            continue
        allz = sorted(z for v in groups.values() for z in v)
        if allz[-1] - allz[0] > 0.5:
            out.append(Finding('R29', 'error', 'Drawer %s: slide holes at different heights (%s); the box will twist and bind.'
                               % (tag, ', '.join('%s %s' % (k, '/'.join('%g' % z for z in sorted(v))) for k, v in groups.items())), 'S'))
    return out


@rule('R30', 'Every part\'s quantity in the parts list equals the number of places it is used in the 3D assembly')
def completeness(d):
    used = Counter(a['code'] for a in d.asm)
    out = []
    for p in d.parts:
        if p['code'] in used and used[p['code']] != p['qty']:
            out.append(Finding('R30', 'error', '%s "%s": parts list says %d, the assembled chest needs %d.'
                               % (p['code'], p['name'], p['qty'], used[p['code']]), p['code']))
    return out


@rule('R31', 'Board left between a groove and the nearest edge is at least as wide as the groove')
def groove_wall(d):
    out = []
    for p in d.parts:
        for o in nestlib.classify(p, []):
            if o[0] != 'GROOVE':
                continue
            y1, y2 = sorted((o[1], o[2]))
            w, wall = y2 - y1, min(y1, p['B'] - y2)
            if wall < w:
                out.append(Finding('R31', 'error', '%s: only %.1f mm of board under a %.1f mm groove; it breaks off.' % (p['code'], wall, w), p['code']))
                break
    return out
