#!/usr/bin/env python3
"""Rebuild demo/index.html from score_history.jsonl + loop_log.jsonl + the rule registry.
    python3 demo/build.py"""
import json, os, re, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import fc.design  # noqa: E402,F401  (puts the generator on sys.path)
from fc.core import load_rules  # noqa: E402

def jl(fn):
    p = os.path.join(HERE, fn)
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []

hist = [{k: h.get(k) for k in ('t', 'note', 'train_n', 'train_caught', 'train_gen', 'mined_n', 'mined_caught',
                                'heldout_n', 'heldout_caught', 'heldout_gen', 'false_pos', 'good_n', 'rules')} for h in jl('score_history.jsonl')]
loop = [{k: e.get(k) for k in ('t', 'step', 'fault', 'rule', 'accepted', 'false_alarms', 'lost', 'n')} for e in jl('loop_log.jsonl')]
rules = []
for rid, fn in sorted(load_rules().items()):
    mod = sys.modules[fn.__module__].__file__
    rules.append(dict(id=rid, desc=fn.desc, auto='_auto_' in os.path.basename(mod)))
try:
    sys.path.insert(0, HERE)
    import faults.mined as fm
    mined = [dict(id=f.id, title=f.title) for f in fm.FAULTS]
except Exception:
    mined = []
def short(n):
    if n.startswith('baseline'): return 'Generator only'
    if n.startswith('R01'): return '+ DXF checks'
    if n.startswith('R03'): return '+ 3D joints'
    if n.startswith('R05'): return '+ 7 rules'
    if n.startswith('R08 fix'): return 'False-alarm fix'
    m = re.match(r'loop: r(\d+)_auto', n)
    if m: return 'Loop R' + m.group(1)
    return n[:14]
for h in hist:
    h['label'] = short(h['note'] or '')
opt_hist = jl('optimize_history.jsonl')
opt = json.load(open(os.path.join(HERE, 'optimize_result.json'))) if os.path.exists(os.path.join(HERE, 'optimize_result.json')) else None
data = dict(hist=hist, loop=loop, rules=rules, mined=mined, opt_hist=[{k: e[k] for k in ('n', 'strict', 'cost', 'ok', 'best')} for e in opt_hist], opt=opt)
tpl = open(os.path.join(HERE, 'demo', 'template.html')).read()
open(os.path.join(HERE, 'demo', 'index.html'), 'w').write(tpl.replace('/*DATA*/null', json.dumps(data)))
print('wrote demo/index.html', len(hist), 'scores', len(loop), 'loop steps', len(rules), 'rules')
