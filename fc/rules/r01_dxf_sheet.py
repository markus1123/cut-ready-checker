"""What the CNC operator imports must be sane on its own: units, sheet bounds, spacing, cut depths."""
import os, re
from fc.core import rule, Finding
from fc.dxfread import layer_num


def contours(sh):
    return [e for e in sh['ents'] if e['type'] == 'POLYLINE' and e.get('layer', '').startswith('10_KONTUR')]


@rule('R01', 'DXF sheet sanity: mm units, parts inside the sheet, spacing >= bit, cut depth vs measured board')
def check(d):
    out = []
    V = d.P['verksted']
    big = V['fres_stor_d']
    thk = {s['plate']: s['tykkelse'] for s in d.summary['plater']}
    for sh in d.sheets:
        raw = open(os.path.join(d.out, sh['file'])).read()
        m = re.search(r'\$INSUNITS\n70\n(\d+)', raw)
        if not m or m.group(1) != '4':
            out.append(Finding('R01', 'error', '%s: DXF units are not mm ($INSUNITS=%s).' % (sh['file'], m.group(1) if m else '?')))
        t = thk.get(sh['file'])
        cs = contours(sh)
        for c in cs:
            x0, y0, x1, y1 = c['bbox']
            if x0 < big or y0 < big or x1 > sh['W'] - big or y1 > sh['H'] - big:
                out.append(Finding('R01', 'error', '%s: a part at (%.0f, %.0f) is outside the sheet or closer than one bit '
                                   'diameter (%.2f) to its edge.' % (sh['file'], x0, y0, big)))
            z = layer_num(c['layer'], 'Z')
            if t and z is not None and z < t - 0.01:
                out.append(Finding('R01', 'error', '%s: contour depth Z%g is less than the measured board %.2f mm - parts '
                                   'will not be cut through.' % (sh['file'], z, t)))
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                a, b = cs[i]['bbox'], cs[j]['bbox']
                gx = max(b[0] - a[2], a[0] - b[2]); gy = max(b[1] - a[3], a[1] - b[3])
                gap = max(gx, gy)
                if gap < big + 1:
                    out.append(Finding('R01', 'error', '%s: two parts are %.1f mm apart (overlap if negative); need >= bit '
                                       'Ø%.2f + 1 mm.' % (sh['file'], gap, big)))
        for e in sh['ents']:
            L = e.get('layer', '')
            z = layer_num(L, 'Z')
            if t and z is not None and (L.startswith('01_') or L.startswith('03_') or L.startswith('04_')):
                if z > t - V['min_restvegg_blindhull']:
                    out.append(Finding('R01', 'error', '%s: blind op on %s is %g deep in a %.2f mm board.' % (sh['file'], L, z, t)))
    return out
