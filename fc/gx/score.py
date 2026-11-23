"""Scoreboard for the generic (any designer) track.

    python3 -m fc.gx.score                  # full report
    python3 -m fc.gx.score --json           # machine-readable (loop)
    python3 -m fc.gx.score --log "note"     # also append to gx_score_history.jsonl
    python3 -m fc.gx.score --show gt04      # mutants of one fault type that are missed, with what rules say
    python3 -m fc.gx.score --fp             # which good designs are flagged, and why

Sets:
  train    = faults/gx_train.py + gx_mined.py types x good_train designs   (agents may look)
  transfer = faults/gx_train.py types  x good_heldout designs (same faults, unseen designs)
  heldout  = faults/gx_heldout.py types x good_heldout designs (unseen faults, unseen designs; never shown)
  fp       = good_train + good_heldout flagged with any error  (target 0)
  noise    = anonymous / unknown-build designs: flag rate + rule crashes (report only)
A mutant is caught if it gets an error finding (rule, part) its unmutated base did not have.
"""
import importlib, json, os, random, sys, time
from . import corpus, core

HERE = corpus.HERE
K = int(os.environ.get('GX_K', 12))   # mutants per fault type


def fault_types(name):
    sys.path.insert(0, HERE)
    try:
        m = importlib.import_module('faults.' + name)
        return m.FAULTS
    except ModuleNotFoundError:
        return []


def _base(designs):
    out = []
    for g in designs:
        f, cr = core.run(g)
        out.append((g, core.error_keys(f), f, cr))
    return out


def mutants(muts, bases, k=K):
    for m in muts:
        n = 0
        order = list(range(len(bases)))
        random.Random(m.id).shuffle(order)
        for i in order:
            if n >= k: break
            g, keys, _, _ = bases[i]
            try:
                mg = m.fn(g, random.Random('%s|%s' % (m.id, g.id)))
            except Exception:
                mg = None
            if mg is None: continue
            n += 1
            yield m, g, keys, mg


def catch(muts, bases, detail=False):
    per = {}
    rows = []
    for m, g, keys, mg in mutants(muts, bases):
        f, cr = core.run(mg)
        new = core.error_keys(f) - keys
        c = per.setdefault(m.id, dict(title=m.title, n=0, caught=0))
        c['n'] += 1; c['caught'] += bool(new)
        if detail: rows.append(dict(fault=m.id, design=g.id, caught=bool(new), new=sorted(map(str, new))[:3],
                                    findings=[(x.rule, x.severity, x.msg) for x in f][:8]))
    rate = lambda d: round(sum(v['caught'] / v['n'] for v in d.values()) / len(d), 3) if d else None
    return dict(types=per, macro=rate(per), mutants=sum(v['n'] for v in per.values()),
                caught=sum(v['caught'] for v in per.values())), rows


def evaluate(show=None):
    t0 = time.time()
    gtr = _base(corpus.designs('good_train')); gho = _base(corpus.designs('good_heldout'))
    noise = _base(corpus.designs('noise'))
    tr, ho = fault_types('gx_train') + fault_types('gx_mined'), fault_types('gx_heldout')
    res = dict(rules=sorted(core.load_rules()), n_good_train=len(gtr), n_good_heldout=len(gho), n_noise=len(noise))
    res['train'], rows = catch(tr, gtr, detail=bool(show))
    res['transfer'], _ = catch(tr, gho)
    res['heldout'], _ = catch(ho, gho)
    fp = [(g.id, sorted({x for x in keys})) for g, keys, f, cr in gtr + gho if keys]
    res['fp'] = dict(n=len(fp), train=sum(1 for g, k, f, c in gtr if k), heldout=sum(1 for g, k, f, c in gho if k),
                     train_ids=sorted(g.id for g, k, f, c in gtr if k))
    res['noise'] = dict(flag_rate=round(sum(1 for b in noise if b[1]) / max(1, len(noise)), 3),
                        crashes={r: sum(1 for b in gtr + gho + noise if r in b[3]) for r in res['rules']})
    res['crashes_good'] = sum(1 for b in gtr + gho if b[3])
    res['secs'] = round(time.time() - t0, 1)
    return res, rows, gtr + gho


def main():
    a = sys.argv[1:]
    show = a[a.index('--show') + 1] if '--show' in a else None
    res, rows, goods = evaluate(show)
    if '--json' in a:
        print(json.dumps(res)); return
    if show:
        for r in rows:
            if r['fault'] == show and not r['caught']:
                print('MISSED', r['design']); [print('    ', x) for x in r['findings']]
        return
    if '--fp' in a:
        for g, keys, f, cr in goods:
            if keys:
                print(g.id); [print('    [%s] %s' % (x.rule, x.msg)) for x in f if x.severity == 'error'][:6]
        return
    print('rules: %s' % ', '.join(res['rules']))
    print('designs: good_train %d, good_heldout %d, noise %d   (%.0fs)' % (res['n_good_train'], res['n_good_heldout'], res['n_noise'], res['secs']))
    for s in ('train', 'transfer', 'heldout'):
        r = res[s]
        print('\n== %s: macro catch %s  (%d/%d mutants)' % (s, r['macro'], r['caught'], r['mutants']))
        if s != 'heldout':
            for k, v in sorted(r['types'].items()):
                print('   %-5s %2d/%-2d  %s' % (k, v['caught'], v['n'], v['title']))
    print('\nfalse alarms on built designs: %d (train %d, heldout %d)' % (res['fp']['n'], res['fp']['train'], res['fp']['heldout']))
    print('noise flag rate %.0f%%, rule crashes %s' % (100 * res['noise']['flag_rate'], {k: v for k, v in res['noise']['crashes'].items() if v}))
    if '--log' in a:
        e = dict(t=time.strftime('%Y-%m-%dT%H:%M:%S'), note=a[a.index('--log') + 1], rules=len(res['rules']),
                 train=res['train']['macro'], transfer=res['transfer']['macro'], heldout=res['heldout']['macro'],
                 fp=res['fp']['n'], noise_flag=res['noise']['flag_rate'])
        open(os.path.join(HERE, 'gx_score_history.jsonl'), 'a').write(json.dumps(e) + '\n')


if __name__ == '__main__':
    main()
