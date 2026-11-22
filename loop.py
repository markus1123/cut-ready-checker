#!/usr/bin/env python3
"""Recursive self-improvement loop for the checker.

    python3 loop.py --mine 6        # miner: an agent writes 6 new realistic faults into faults/mined.py
    python3 loop.py --iters 5       # writer: for each missed train/mined fault, an agent writes ONE rule
    python3 loop.py --mine 6 --iters 8

Acceptance gate for a new rule (plain code, never an LLM opinion at check time):
  * catches the fault it was written for,
  * every fault caught before is still caught (no regression),
  * zero errors on the known-good designs (faults/good.py),
The held-out set (faults/heldout.py) is NEVER shown to the agents; it is only scored, to measure generalisation.
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fc import score  # noqa: E402

CLAUDE = os.environ.get('CLAUDE_BIN', 'claude')
MODEL = os.environ.get('FC_MODEL', '')


def agent(prompt, tools='Read,Write,Edit,Bash,Glob,Grep'):
    cmd = [CLAUDE, '-p', prompt, '--allowedTools', tools, '--permission-mode', 'acceptEdits']
    if MODEL:
        cmd += ['--model', MODEL]
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL)
    return r.stdout[-2000:]


def snapshot():
    # fresh process: newly written / rejected rule modules must not linger in the registry
    code = ('import json,sys; sys.path.insert(0,"."); from fc import score; '
            'print(json.dumps(score.evaluate(["train","mined","good"], verbose=False)))')
    res = json.loads(subprocess.run([sys.executable, '-c', code], cwd=HERE, capture_output=True, text=True).stdout.strip().split('\n')[-1])
    caught = {r['id'] for n in ('train', 'mined') for r in res[n] if r['caught']}
    missed = [r for n in ('train', 'mined') for r in res[n] if not r['caught']]
    fp = [r['id'] for r in res['good'] if r['caught']]
    return caught, missed, fp


RULE_BRIEF = """You are improving a DFM checker for CNC-cut flat-pack furniture (repo: this directory; read README.md,
fc/core.py, fc/design.py, fc/world.py, and 2-3 existing rules in fc/rules/ first). The generator that is checked lives in
../kommode-bestilling/generator (kommode.py, nestlib.py) - read but DO NOT modify it.

The checker currently MISSES this seeded fault (see faults/{fset}.py, id {fid}):
  title: {title}
  why it matters: {why}
Run `python3 -m fc.score --show {fid}` to see what every layer says and to get the generated files in .work/{fid}.

Write ONE new rule file fc/rules/{fname}.py using the @rule decorator (id {rid}) that catches this fault for the
right physical reason, stated generally (it must also catch variants of the fault, and must NOT trigger on the
known-good designs in faults/good.py: check with `python3 -m fc.score`). Rules are plain deterministic Python with
concrete thresholds and a docstring that states the workshop reason. Do not edit other rules, faults, or the
scoring code. Do not open faults/heldout.py. Finish with a one-line summary of the rule."""

MINE_BRIEF = """You are the rule MINER for a CNC flat-pack furniture checker (this directory; read README.md, fc/design.py,
fc/core.py, faults/train.py and faults/helpers.py; the generator is ../kommode-bestilling/generator/kommode.py).
Do not open faults/heldout.py or fc/rules/.
Add {n} NEW faults to faults/mined.py (create it like faults/train.py with FAULTS = [...]; keep existing entries; ids
m01, m02, ... continuing). Each must be a real, documented way flat-pack/CNC/cabinet jobs fail - think Blum/Hettich
mounting instructions, Minifix/dowel spacing rules, ShopBot/VCarve forum failure stories, edge-banding and
grain rules, hold-down, tool reach, assembly access - NOT a copy of a train fault. Put the source in source=.
Each fault must actually change the generated output (verify with `python3 -m fc.score --show mNN`) and must be a
genuine defect. Finish with the list of ids and titles."""


def next_rid():
    ids = [f for f in os.listdir(os.path.join(HERE, 'fc', 'rules')) if f.startswith('r') and f[1:3].isdigit()]
    return max(int(f[1:3]) for f in ids) + 1


def log(entry):
    entry['t'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    with open(os.path.join(HERE, 'loop_log.jsonl'), 'a') as f:
        f.write(json.dumps(entry) + '\n')
    print(json.dumps(entry))


def main():
    a = sys.argv[1:]
    if '--mine' in a:
        n = int(a[a.index('--mine') + 1])
        out = agent(MINE_BRIEF.format(n=n))
        log(dict(step='mine', n=n, agent=out[-400:]))
    iters = int(a[a.index('--iters') + 1]) if '--iters' in a else 0
    tried = set()
    for it in range(iters):
        caught, missed, fp = snapshot()
        missed = [m for m in missed if m['id'] not in tried]
        if not missed:
            print('nothing left to fix'); break
        m = missed[0]; tried.add(m['id'])
        fset = 'mined' if m['id'].startswith('m') else 'train'
        rid = next_rid(); fname = 'r%02d_auto_%s' % (rid, m['id'])
        path = os.path.join(HERE, 'fc', 'rules', fname + '.py')
        out = agent(RULE_BRIEF.format(fset=fset, fid=m['id'], title=m['title'], why='', fname=fname, rid='R%02d' % rid))
        if not os.path.exists(path):
            log(dict(step='write', fault=m['id'], result='no file written', agent=out[-300:])); continue
        caught2, missed2, fp2 = snapshot()
        ok = m['id'] in caught2 and caught <= caught2 and not fp2
        if not ok:
            os.rename(path, path + '.rejected')
        log(dict(step='write', fault=m['id'], rule=fname, accepted=ok, caught_before=len(caught), caught_after=len(caught2),
                 lost=sorted(caught - caught2), false_alarms=fp2, agent=out[-300:]))
        if ok:
            subprocess.run(['python3', '-m', 'fc.score', '--log', 'loop: %s for %s' % (fname, m['id'])], cwd=HERE,
                           capture_output=True)
            subprocess.run(['git', 'add', '-A'], cwd=HERE)
            subprocess.run(['git', '-c', 'user.name=rsi-loop', '-c', 'user.email=noreply@local', 'commit', '-qm',
                            'loop: accept %s (catches %s)' % (fname, m['id'])], cwd=HERE)


if __name__ == '__main__':
    main()
