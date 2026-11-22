"""Minimal reader for the R12 DXFs the generator writes (POLYLINE/VERTEX, CIRCLE, TEXT).
Checks run on these files because they are what the CNC operator imports, not on the generator's intent."""
import os, re


def read(fn):
    lines = open(fn, encoding='ascii', errors='replace').read().split('\n')
    pairs = [(lines[i].strip(), lines[i + 1].rstrip('\r')) for i in range(0, len(lines) - 1, 2)]
    ents, cur, in_ent = [], None, False
    for code, val in pairs:
        if code == '2' and val == 'ENTITIES':
            in_ent = True; continue
        if not in_ent:
            continue
        if code == '0':
            if val in ('POLYLINE', 'CIRCLE', 'TEXT'):
                cur = dict(type=val, pts=[]); ents.append(cur)
            elif val == 'VERTEX' and cur is not None and cur['type'] == 'POLYLINE':
                cur['pts'].append([None, None]); cur['_v'] = True
            elif val in ('SEQEND', 'ENDSEC', 'EOF'):
                cur = None
            continue
        if cur is None:
            continue
        if code == '8' and not cur.get('_v'):
            cur['layer'] = val
        elif cur['type'] == 'POLYLINE' and cur.get('_v') and code in ('10', '20'):
            cur['pts'][-1][0 if code == '10' else 1] = float(val)
        elif cur['type'] in ('CIRCLE', 'TEXT') and code in ('10', '20', '40'):
            cur[{'10': 'x', '20': 'y', '40': 'r' if cur['type'] == 'CIRCLE' else 'h'}[code]] = float(val)
        elif cur['type'] == 'TEXT' and code == '1':
            cur['text'] = val
    for e in ents:
        e.pop('_v', None)
        if e['type'] == 'POLYLINE':
            xs = [p[0] for p in e['pts']]; ys = [p[1] for p in e['pts']]
            e['bbox'] = (min(xs), min(ys), max(xs), max(ys))
    m = re.search(r'_(\d+)x(\d+)\.dxf$', fn)
    return dict(file=os.path.basename(fn), W=int(m.group(1)) if m else None, H=int(m.group(2)) if m else None,
                ents=ents)


def layer_num(layer, key):
    """'01_BOR_D5_Z11' -> layer_num(.., 'Z') = 11.0 ; 'P' is the decimal point."""
    m = re.search(r'_%s([0-9P]+)' % key, layer)
    return float(m.group(1).replace('P', '.')) if m else None
