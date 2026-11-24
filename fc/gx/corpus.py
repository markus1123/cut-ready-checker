"""Which corpus files are used for what.

  good_train    files from designs built by others / by the designer, readable geometry - agents may look at these
  good_heldout  same kind, different designs (split by design id hash) - never shown to agents, scored only
  noise         anonymous / unknown-build designs - only a robustness + flag-rate report, never a gate
"""
import json, os, hashlib, re
from . import model

TH_NAME = re.compile(r'(?i)(?<![\d.])(\d{1,2}(?:[.,]\d)?)\s?mm(?![\w-]*diam)')   # '15 mm', '12mm material', '18.5mm'
TH_OK = (3.0, 40.0)


def thickness_from_name(path):
    """Sheet thickness stated in the file or folder name (Fellesverkstedet 'HOK systems Worktop CNC-file 15 mm')."""
    for part in reversed(path.split('/')[-3:]):
        m = TH_NAME.findall(part)
        vals = [float(v.replace(',', '.')) for v in m if TH_OK[0] <= float(v.replace(',', '.')) <= TH_OK[1]]
        if vals: return vals[-1]
    return None


def _web_thickness():
    out = {}
    p = os.path.join(C, 'web_manifest.jsonl')
    if os.path.exists(p):
        for l in open(p):
            w = json.loads(l)
            if w.get('material_thickness_mm'):
                out[os.path.relpath(w['local_dir'], os.path.join(C, 'raw'))] = float(w['material_thickness_mm'])
    return out

HERE = model.HERE
C = os.environ.get('FC_CORPUS') or os.path.join(HERE, 'corpus')   # private corpus checkout in the cloud
X_FILE = os.path.join(HERE, 'corpus', 'good_exclusions.json')


def _usable():
    P = {}
    for l in open(os.path.join(C, 'profiles.jsonl')):
        p = json.loads(l)
        if 'error' not in p and p['loops'] > 0 and p['open_chains'] <= 0.1 * (p['loops'] + p['open_chains']):
            P[p['path']] = p
    return P


def exclusions():
    """Human-reviewed: built-set files that turned out to be genuinely faulty (path -> reason)."""
    return json.load(open(X_FILE)) if os.path.exists(X_FILE) else {}


def files(split):
    U = _usable(); out = []; X = exclusions(); WT = _web_thickness()
    for l in open(os.path.join(C, 'designs.jsonl')):
        d = json.loads(l)
        if d['category'] != 'furniture' or d['duplicate_of'] or d['all_files_duplicated']:
            continue
        built = d['built_by_others'] in ('yes', 'by_designer')
        h = int(hashlib.sha1(d['id'].encode()).hexdigest(), 16) % 100
        s = ('good_train' if h < 60 else 'good_heldout') if built else 'noise'
        if s != split: continue
        for f in d['files']:
            if f['dup_of'] or f['path'] not in U or (s != 'noise' and f['path'] in X): continue
            meta = dict(design=d['id'], name=d['name'], tier=d.get('source_tier'), built=d['built_by_others'],
                        type=d['furniture_type'], licence=d['licence'])
            wt = next((v for k, v in WT.items() if d['dir'] == k or d['dir'].startswith(k + '/')), None)
            nt = thickness_from_name(f['path'])
            if wt: meta.update(thickness_mm=wt, thickness_source='manifest')
            elif nt: meta.update(thickness_mm=nt, thickness_source='filename')
            out.append((os.path.join(C, 'raw', f['path']), d['units'], meta, f['path']))
    return sorted(out, key=lambda t: t[3])


def designs(split, limit=None):
    """Yield GDesigns (cached parse). Files that fail to parse or have no parts are skipped."""
    n = 0
    for fn, units, meta, rel in files(split):
        try:
            g = model.load(fn, units, meta, rel)
        except Exception:
            continue
        if not g.parts: continue
        yield g; n += 1
        if limit and n >= limit: break
