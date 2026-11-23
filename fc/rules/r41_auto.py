"""R41 mating fit: what is cut must fit the part it is joined to in the assembled chest.

Every joint is two parts and a piece of hardware. A part or a hole can be internally plausible and still not fit its
mate, because one of the two sides was computed from the wrong variable or the wrong hardware field. Three checks:

(a) Part = its place. A part's cut size (L x B x t, any orientation) equals the box the 3D assembly gives it,
    within 1.0 mm. Reason: panel saw / CNC tolerance on furniture parts is +-0.5 mm; a back, bottom or side that
    differs by more than 1 mm from its opening leaves a gap or does not go in (and the carcass is not squared).
(b) Pass hole >= grip hole. Where a fastener crosses a joint, the hole it passes through (the through hole, or the
    hole that runs into the fastener's cam housing) must be larger than the hole its thread grips in the mate.
    Häfele Minifix 15: bolt thread in a Ø5 hole, shank through a Ø8 edge bore; confirmat 7x50: Ø7 pass, Ø5 pilot;
    wood screws 4x40: Ø4.5 pass, Ø3 pilot. A grip hole as big as the pass hole gives the thread nothing to bite,
    and a pass hole smaller than the grip hole means the fastener cannot get through.
    Dowels are a press fit in both parts: the two coaxial dowel holes have the same Ø within 0.2 mm (Häfele/Wolfcraft
    dowel drilling: hole = dowel Ø, +0.1..0.2 mm).
(c) Hole count across the joint. An operation that is done at assembly "through the holes in the mating part" and
    names a hole count (e.g. handle holes "(2 stk)") needs that many machined holes of the same hardware in the
    touching part, on every instance. Otherwise the fitter has nothing to drill through and marks by hand on a
    finished face.
"""
import re
from fc.core import rule, Finding
from fc.world import frames, holes, inside, add, mul, neg, dot
from fc.geom import seg_dist

SIZE_TOL = 1.0
COAX_TOL = 0.6
DOWEL_TOL = 0.2
FAMILIES = [('Minifix-bolt', 'minifix'), ('Plugg', 'dowel'), ('Konfirmat', 'confirmat'), ('Skrue til list', 'screw'),
            ('Forbor skrue', 'screw'), ('Håndtak', 'handle'), ('Skinne', 'slide')]
SCREWS = {'minifix', 'confirmat', 'screw'}
NOT_PARTS = {'BEIN', 'SKINNE'}          # bought hardware placed in the assembly, not cut


def fam(note):
    return next((f for p, f in FAMILIES if note.startswith(p)), None)


def _seg(h):
    return h['entry'], add(h['entry'], mul(h['dir'], h['depth']))


def _housings(f):
    return [h for h in holes(f) if 'hus' in h['op']['note'].lower() and h['d'] >= 12]


def _is_pass(f, h):
    if h['op']['kind'] == 'through':
        return True
    p, q = _seg(h)
    return any(seg_dist(p, q, *_seg(c)) < c['d'] / 2 for c in _housings(f))


def part_size(d):
    out, seen = [], set()
    for a in d.asm:
        p = d.by.get(a['code'])
        if p is None or a['code'] in NOT_PARTS or a['code'] in seen:
            continue
        cut = sorted((p['L'], p['B'], p['t']))
        place = sorted(a['b'][3:6])
        if any(abs(c - b) > SIZE_TOL for c, b in zip(cut, place)):
            seen.add(a['code'])
            out.append(Finding('R41', 'error', '%s "%s" is cut %s but its place in the assembled chest (%s) is %s; it will not fit.'
                               % (p['code'], p['name'], ' x '.join('%g' % v for v in (p['L'], p['B'], p['t'])), a['label'],
                                  ' x '.join('%.1f' % v for v in a['b'][3:6])), p['code']))
    return out


def hole_pairs(d):
    inst = frames(d)
    out, seen = [], set()
    for f in inst:
        for h in holes(f):
            a = fam(h['op']['note'])
            if a not in SCREWS and a != 'dowel':
                continue
            probe = add(h['entry'], mul(h['dir'], -0.5))
            mates = [g for g in inst if g is not f and inside(g['box'], probe)]
            if not mates:
                continue
            g = mates[0]
            gh = next((x for x in holes(g) if dot(x['dir'], h['dir']) < -0.99
                       and sum((p - q) ** 2 for p, q in zip(x['entry'], h['entry'])) ** 0.5 < COAX_TOL), None)
            if gh is None:
                continue                      # missing partner is R03's job
            key = tuple(sorted([(f['code'], h['op']['note'], h['d']), (g['code'], gh['op']['note'], gh['d'])]))
            if key in seen:
                continue
            seen.add(key)
            if a == 'dowel':
                if abs(h['d'] - gh['d']) > DOWEL_TOL:
                    out.append(Finding('R41', 'error', 'Dowel joint %s/%s: Ø%g hole meets Ø%g hole; a dowel is a press fit in both.'
                                       % (f['code'], g['code'], h['d'], gh['d']), f['code']))
                continue
            ph, pg = _is_pass(f, h), _is_pass(g, gh)
            if ph == pg:
                continue
            (pf, pass_h), (gf, grip_h) = ((f, h), (g, gh)) if ph else ((g, gh), (f, h))
            if pass_h['d'] <= grip_h['d']:
                out.append(Finding('R41', 'error', '%s joint %s->%s: the fastener passes through Ø%g in %s but grips in Ø%g in %s; '
                                   'the pass hole must be larger than the thread hole.'
                                   % (h['op']['note'].split(' ')[0], pf['code'], gf['code'], pass_h['d'], pf['code'], grip_h['d'], gf['code']), gf['code']))
    return out


def hole_count(d):
    inst = frames(d)
    out, seen = [], set()
    for f in inst:
        for o in f['part']['ops']:
            if o['kind'] != 'manual':
                continue
            m = re.search(r'\((\d+)\s*stk\)', o['note'])
            a = fam(o['note'])
            if not m or a is None:
                continue
            need = int(m.group(1))
            x, y, z, dx, dy, dz = f['box']
            c = (x + dx / 2, y + dy / 2, z + dz / 2)
            t = f['part']['t']
            for s in (1, -1):
                probe = add(c, mul(f['n'], s * (t / 2 + 0.5)))
                for g in inst:
                    if g is f or not inside(g['box'], probe):
                        continue
                    have = sum(1 for gh in holes(g) if gh['end'] != 'F2' and fam(gh['op']['note']) == a)
                    key = (f['code'], g['code'], o['note'])
                    if have < need and key not in seen:
                        seen.add(key)
                        out.append(Finding('R41', 'error', '%s "%s" is drilled at assembly through %d holes in %s, but %s (%s) has %d.'
                                           % (f['code'], o['note'], need, g['code'], g['code'], g['label'], have), g['code']))
    return out


@rule('R41', 'Mating fit: each part matches its place in the assembly; joint holes pass>grip, dowel holes equal, hole counts agree')
def check(d):
    return part_size(d) + hole_pairs(d) + hole_count(d)
