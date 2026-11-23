"""Scoreboard: run every fault through generator + rules, report catch rate and false positives.

    python3 -m fc.score                 # train + heldout + good
    python3 -m fc.score --log "note"    # also append a line to score_history.jsonl
    python3 -m fc.score --show f07      # show what each layer says about one fault
"""
import importlib, json, os, sys, time
from . import design
from .core import verdict, gen_errors, run_rules, load_rules

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETS = ['train', 'mined', 'retired', 'heldout', 'good']   # retired = an old held-out set whose faults have been seen


def load_set(name):
    sys.path.insert(0, HERE)
    try:
        return importlib.import_module('faults.' + name).FAULTS
    except ModuleNotFoundError:
        return []


def evaluate(names=SETS, verbose=True):
    res = {}
    for name in names:
        rows = []
        for f in load_set(name):
            d = design.make(fault=f)
            try:
                g = bool(gen_errors(d))
                caught, msgs = verdict(d)
            finally:
                design.cleanup(d)
            rows.append(dict(id=f.id, title=f.title, gen=g, caught=caught, msgs=msgs, good=f.good))
        res[name] = rows
    return res


def summarize(res):
    s = {}
    for name, rows in res.items():
        if name == 'good':
            s['false_pos'] = sum(r['caught'] for r in rows)
            s['good_n'] = len(rows)
        else:
            s[name + '_n'] = len(rows)
            s[name + '_gen'] = sum(r['gen'] for r in rows)
            s[name + '_caught'] = sum(r['caught'] for r in rows)
    s['rules'] = len(load_rules())
    try:
        s['heldout_v'] = getattr(importlib.import_module('faults.heldout'), 'VERSION', 1)
    except ModuleNotFoundError:
        pass
    return s


def main():
    a = sys.argv[1:]
    if '--show' in a:
        fid = a[a.index('--show') + 1]
        for name in SETS:
            for f in load_set(name):
                if f.id == fid:
                    d = design.make(fault=f, keep=os.path.join(HERE, '.work', fid))
                    print(f.title, '\n  why:', f.why)
                    print('generator:'); [print('  ', m) for m in gen_errors(d)]
                    print('rules:'); [print('  [%s] %s %s' % (x.severity, x.rule, x.msg)) for x in run_rules(d)]
                    print('files in', d.out)
                    return
        sys.exit('no fault ' + fid)
    res = evaluate()
    s = summarize(res)
    for name in SETS:
        print('\n== %s ==' % name)
        for r in res[name]:
            if r['good']:
                mark = 'FALSE ALARM' if r['caught'] else 'ok (clean)'
            else:
                mark = ('gen  ' if r['gen'] else '     ') + ('CAUGHT' if r['caught'] else 'MISSED')
            print('  %-5s %-13s %s' % (r['id'], mark, r['title']))
            if r['good'] and r['caught'] or ('-v' in a and r['msgs']):
                for m in r['msgs'][:4]:
                    print('          ', m[:160])
    print()
    for name in ('train', 'mined', 'retired', 'heldout'):
        if s.get(name + '_n'):
            print('%-8s generator alone %2d/%-2d (%3.0f%%)   generator + rules %2d/%-2d (%3.0f%%)' % (
                name, s[name + '_gen'], s[name + '_n'], 100 * s[name + '_gen'] / s[name + '_n'],
                s[name + '_caught'], s[name + '_n'], 100 * s[name + '_caught'] / s[name + '_n']))
    print('false alarms on known-good designs: %d/%d    rules: %d' % (s['false_pos'], s['good_n'], s['rules']))
    if '--log' in a:
        note = a[a.index('--log') + 1] if len(a) > a.index('--log') + 1 else ''
        s.update(t=time.strftime('%Y-%m-%dT%H:%M:%S'), note=note,
                 missed={n: [r['id'] for r in res[n] if not r['caught']] for n in ('train', 'mined', 'retired', 'heldout') if n in res})
        with open(os.path.join(HERE, 'score_history.jsonl'), 'a') as f:
            f.write(json.dumps(s) + '\n')
    return s


if __name__ == '__main__':
    main()
