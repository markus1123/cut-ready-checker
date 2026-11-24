"""The DXF must contain exactly the parts and CNC ops of the cut list / part model - no more, no less."""
import nestlib
from fc.core import rule, Finding
from fc.dxfread import layer_num

TOL = 0.05


def expected_ops(p):
    return nestlib.classify(p, [])


def place(c, L, B):
    """Return list of candidate transforms (part xy -> sheet xy) consistent with the contour bbox."""
    x0, y0, x1, y1 = c['bbox']; w, h = x1 - x0, y1 - y0
    tfs = []
    if abs(w - L) < TOL and abs(h - B) < TOL:
        tfs.append(lambda px, py: (x0 + px, y0 + py))
    if abs(w - B) < TOL and abs(h - L) < TOL:
        tfs.append(lambda px, py: (x0 + py, y0 + L - px))
    return tfs


@rule('R02', 'DXF vs cut list: part count, outline size, and every hole/groove at the right place, diameter, depth')
def check(d):
    out = []
    parts = {p['code']: p for p in d.parts}
    count = {}
    for sh in d.sheets:
        texts = [e for e in sh['ents'] if e['type'] == 'TEXT']
        circles = [e for e in sh['ents'] if e['type'] == 'CIRCLE' and 'HOLDDOWN' not in e.get('layer', '').upper()]   # screw marks sit outside parts on purpose
        grooves = [e for e in sh['ents'] if e['type'] == 'POLYLINE' and e.get('layer', '').startswith('04_NOT')]
        used = set()
        for c in [e for e in sh['ents'] if e['type'] == 'POLYLINE' and e.get('layer', '').startswith('10_KONTUR')]:
            x0, y0, x1, y1 = c['bbox']
            lab = [t for t in texts if x0 <= t['x'] <= x1 and y0 <= t['y'] <= y1]
            if not lab:
                out.append(Finding('R02', 'error', '%s: unlabelled part at (%.0f, %.0f).' % (sh['file'], x0, y0))); continue
            code = lab[0]['text'].split()[0]
            count[code] = count.get(code, 0) + 1
            p = parts.get(code)
            if not p:
                out.append(Finding('R02', 'error', '%s: part %s is not in the cut list.' % (sh['file'], code))); continue
            tfs = place(c, p['L'], p['B'])
            if not tfs:
                out.append(Finding('R02', 'error', '%s: %s outline %.2f x %.2f does not match cut list %g x %g.'
                                   % (sh['file'], code, x1 - x0, y1 - y0, p['L'], p['B']), code)); continue
            inside = [i for i, e in enumerate(circles) if x0 - 0.01 <= e['x'] <= x1 + 0.01 and y0 - 0.01 <= e['y'] <= y1 + 0.01]
            best = None
            for tf in tfs:
                miss, hit = [], set()
                for o in expected_ops(p):
                    if o[0] == 'GROOVE':
                        continue
                    _, x, y, dia, z, note = o
                    X, Y = tf(x, y)
                    m = [i for i in inside if i not in hit and abs(circles[i]['x'] - X) < TOL and abs(circles[i]['y'] - Y) < TOL
                         and abs(2 * circles[i]['r'] - dia) < 0.02]
                    if not m:
                        miss.append('%s Ø%g at (%g, %g)' % (note, dia, x, y)); continue
                    hit.add(m[0])
                    L = circles[m[0]]['layer']
                    if o[0] == 'HOLE':
                        zz = layer_num(L, 'Z')
                        if zz is None or abs(zz - z) > 0.01:
                            miss.append('%s depth %s in DXF vs %g' % (note, zz, z))
                    elif 'GJENNOM' not in L:
                        miss.append('%s should be through, layer %s' % (note, L))
                extra = [i for i in inside if i not in hit]
                score = len(miss) + len(extra)
                if best is None or score < best[0]:
                    best = (score, miss, extra)
            _, miss, extra = best
            used.update(inside)
            for m in miss[:3]:
                out.append(Finding('R02', 'error', '%s: %s - %s missing/wrong in the DXF.' % (sh['file'], code, m), code))
            if extra:
                out.append(Finding('R02', 'error', '%s: %s has %d hole(s) in the DXF that are not in the part model.'
                                   % (sh['file'], code, len(extra)), code))
            ng = sum(1 for o in expected_ops(p) if o[0] == 'GROOVE')
            gin = [g for g in grooves if x0 - 0.01 <= g['bbox'][0] and g['bbox'][2] <= x1 + 0.01 and y0 - 0.01 <= g['bbox'][1] and g['bbox'][3] <= y1 + 0.01]
            if len(gin) != ng:
                out.append(Finding('R02', 'error', '%s: %s has %d groove(s) in the DXF, model says %d.' % (sh['file'], code, len(gin), ng), code))
        stray = [e for i, e in enumerate(circles) if i not in used]
        if stray:
            out.append(Finding('R02', 'error', '%s: %d hole(s) outside every part.' % (sh['file'], len(stray))))
    for code, p in parts.items():
        if count.get(code, 0) != p['qty']:
            out.append(Finding('R02', 'error', 'Cut list says %d x %s, the DXFs contain %d.' % (p['qty'], code, count.get(code, 0)), code))
    return out
