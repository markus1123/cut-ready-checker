"""Read the cutting files back the way the CAM software will, and check they still describe the parts.

R32 contours: every cut outline is a closed, simple (non-self-crossing) polygon. An open outline is not cut as a
    part; a crossing one makes the toolpath cut through the part.
R33 labels and inside/outside: every part label sits on the label layer, inside exactly one outer outline, and
    every outer outline has one label; inside cuts lie within a part. Text on a cutting layer is engraved/cut;
    an outer outline marked as inside is cut on the wrong side of the line (part comes out one bit diameter small).
R34 drill layers: the diameter written in a drill/pocket layer name equals the circle actually drawn on it.
    The operator picks the tool from the layer name, so a Ø15 pocket on a 'D5' layer is drilled with the wrong bit.
R35 board per sheet: every part on a sheet file is a part that is made of the board named in that file.
"""
import re
from fc.core import rule, Finding
from fc.dxfread import layer_num

CUT = '10_KONTUR'


def _closed(e):
    pts = e['pts']
    return bool(e.get('flags', 0) & 1) or (len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6)


def _cross(a, b, c, d):
    o = lambda p, q, r: (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2, d3, d4 = o(c, d, a), o(c, d, b), o(a, b, c), o(a, b, d)
    return (d1 * d2 < -1e-9) and (d3 * d4 < -1e-9)


def _simple(pts):
    P = pts + [pts[0]] if pts[0] != pts[-1] else pts
    segs = list(zip(P, P[1:]))
    for i in range(len(segs)):
        for j in range(i + 2, len(segs)):
            if i == 0 and j == len(segs) - 1:
                continue
            if _cross(*segs[i], *segs[j]):
                return False
    return True


def _inside(pt, pts):
    x, y, c = pt[0], pt[1], False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _sheets(d):
    return [s for s in d.sheets]


@rule('R32', 'Every cut outline in the DXF files is closed and does not cross itself')
def contours(d):
    out = []
    for sh in _sheets(d):
        for e in sh['ents']:
            if e['type'] != 'POLYLINE' or not e.get('layer', '').startswith(CUT):
                continue
            if not _closed(e):
                out.append(Finding('R32', 'error', '%s: an outline on %s is open; CAM will not cut it as a part.' % (sh['file'], e['layer'])))
            elif not _simple(e['pts']):
                out.append(Finding('R32', 'error', '%s: an outline on %s crosses itself; the toolpath would cut through the part.' % (sh['file'], e['layer'])))
    return out


@rule('R33', 'Labels sit on the label layer, one inside each part; outer/inner outlines are where they belong')
def labels(d):
    out = []
    for sh in _sheets(d):
        E = sh['ents']
        outer = [e for e in E if e['type'] == 'POLYLINE' and e.get('layer', '').startswith(CUT) and 'INNVENDIG' not in e['layer']]
        inner = [e for e in E if e['type'] == 'POLYLINE' and e.get('layer', '').startswith(CUT) and 'INNVENDIG' in e['layer']]
        texts = [e for e in E if e['type'] == 'TEXT']
        bad = [t for t in texts if t.get('layer', '').startswith(('10_', '01_', '02_', '03_', '04_'))]
        if bad:
            out.append(Finding('R33', 'error', '%s: %d part labels are on cutting layer %s; they would be engraved or cut.' % (sh['file'], len(bad), bad[0]['layer'])))
        for t in texts:
            n = sum(_inside((t['x'], t['y']), o['pts']) for o in outer)
            if n != 1:
                out.append(Finding('R33', 'error', '%s: label "%s" is inside %d outer outlines (need exactly 1).' % (sh['file'], t.get('text', ''), n)))
                break
        for o in outer:
            if not any(_inside((t['x'], t['y']), o['pts']) for t in texts):
                out.append(Finding('R33', 'error', '%s: a part outline has no label; nobody will know which part it is.' % sh['file']))
                break
        for i in inner:
            c = (sum(p[0] for p in i['pts']) / len(i['pts']), sum(p[1] for p in i['pts']) / len(i['pts']))
            if not any(_inside(c, o['pts']) for o in outer):
                out.append(Finding('R33', 'error', '%s: an inside cut is not inside any part; it is a part outline cut on the wrong side of the line.' % sh['file']))
                break
    return out


@rule('R34', 'The diameter in each drill/pocket layer name equals the circles drawn on it')
def drill_layers(d):
    out, seen = [], set()
    for sh in _sheets(d):
        for e in sh['ents']:
            if e['type'] != 'CIRCLE':
                continue
            D = layer_num(e.get('layer', ''), 'D')
            if D is None:
                continue
            if abs(2 * e['r'] - D) > 0.2 and (sh['file'], e['layer']) not in seen:
                seen.add((sh['file'], e['layer']))
                out.append(Finding('R34', 'error', '%s: Ø%.1f circles on layer %s; the operator will drill them with a Ø%g bit.' % (sh['file'], 2 * e['r'], e['layer'], D)))
    return out


@rule('R35', 'Every part on a sheet file is made of the board that file is named after')
def board_per_sheet(d):
    mat_of = {p['code']: d.P['_valg'][p['mat']]['id'] for p in d.parts if p.get('mat') in d.P['_valg']}
    out = []
    for sh in _sheets(d):
        m = re.match(r'^[a-z]+\d+_(.+)_\d+x\d+\.dxf$', sh['file'])
        if not m:
            continue
        board = m.group(1)
        wrong = sorted({t['text'].split(' ')[0] for t in sh['ents'] if t['type'] == 'TEXT' and t.get('text')
                        and t['text'].split(' ')[0] in mat_of and mat_of[t['text'].split(' ')[0]] != board})
        if wrong:
            out.append(Finding('R35', 'error', '%s holds %s, which are not made of %s; they would be cut from the wrong board.' % (sh['file'], ', '.join(wrong), board)))
    return out
