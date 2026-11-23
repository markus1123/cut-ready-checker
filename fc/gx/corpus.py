"""Which corpus files are used for what.

  good_train    files from designs built by others / by the designer, readable geometry - agents may look at these
  good_heldout  same kind, different designs (split by design id hash) - never shown to agents, scored only
  noise         anonymous / unknown-build designs - only a robustness + flag-rate report, never a gate
"""
import json, os, hashlib
from . import model

HERE = model.HERE
C = os.path.join(HERE, 'corpus')


def _usable():
    P = {}
    for l in open(os.path.join(C, 'profiles.jsonl')):
        p = json.loads(l)
        if 'error' not in p and p['loops'] > 0 and p['open_chains'] <= 0.1 * (p['loops'] + p['open_chains']):
            P[p['path']] = p
    return P


def exclusions():
    """Human-reviewed: built-set files that turned out to be genuinely faulty (path -> reason)."""
    p = os.path.join(C, 'good_exclusions.json')
    return json.load(open(p)) if os.path.exists(p) else {}


def files(split):
    U = _usable(); out = []; X = exclusions()
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
