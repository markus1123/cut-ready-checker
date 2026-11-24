#!/usr/bin/env python3
"""Self-improvement loop for the GENERIC checker (any designer's DXF, fc/gx).

    caffeinate -i python3 loop_gx.py --hours 6            # run unattended for up to 6 h
    python3 loop_gx.py --iters 3                          # a few iterations
    options: --mine-every N (default 3: miner adds fault types every N writer steps), --max-tries 2, --model sonnet

Each step: pick the train/mined fault type with the lowest catch rate -> an agent writes ONE rule file -> gate:
  * the target type's catch count goes up,
  * no fault type loses a catch (no regression),
  * still 0 false alarms on the built designs in good_train, and no new rule crashes,
  * the flag rate on the anonymous 'noise' corpus rises by at most 3 points (guard against flag-everything rules).
Accepted rules are committed; rejected ones are kept as .rejected and the reason is fed into the next attempt.
The miner adds new fault types (faults/gx_mined.py) from real workshop sources so the target keeps moving.
Held-out (unseen designs x unseen fault types written by a blind agent) is scored and logged, never shown to agents.
"""
import json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
CLAUDE = os.environ.get('CLAUDE_BIN', 'claude')
LOG = os.path.join(HERE, 'gx_loop_log.jsonl')
RULES = os.path.join(HERE, 'fc', 'gx', 'rules')
MINED = os.path.join(HERE, 'faults', 'gx_mined.py')


def arg(name, default=None, cast=str):
    a = sys.argv[1:]
    return cast(a[a.index(name) + 1]) if name in a else default


MODEL = arg('--model', os.environ.get('FC_MODEL', ''))


def agent(prompt, timeout=1500):
    cmd = [CLAUDE, '-p', prompt, '--allowedTools', 'Read,Write,Edit,Bash,Glob,Grep', '--permission-mode', 'acceptEdits']
    if MODEL: cmd += ['--model', MODEL]
    try:
        r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return r.stdout[-1500:]
    except subprocess.TimeoutExpired:
        return 'TIMEOUT'


def snapshot():
    r = subprocess.run([sys.executable, '-m', 'fc.gx.score', '--json'], cwd=HERE, capture_output=True, text=True)
    return json.loads(r.stdout.strip().split('\n')[-1])


def log(e):
    e['t'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    open(LOG, 'a').write(json.dumps(e) + '\n'); print(json.dumps(e)[:400], flush=True)


def table(res):
    return '\n'.join('  %-6s %2d/%-2d caught  %s' % (k, v['caught'], v['n'], v['title'])
                     for k, v in sorted(res['train']['types'].items()))


WRITE = """You are improving a checker for CNC-cut flat-pack furniture files from ANY designer (repo: this directory).
Read first: corpus/README.md, fc/gx/model.py (how a DXF becomes parts/features in mm), fc/gx/core.py, fc/gx/score.py,
the existing rules in fc/gx/rules/, and the fault type you target in faults/gx_train.py or faults/gx_mined.py.
Workshop knowledge: docs/rules-from-manuals.md, docs/tools-and-rules.md.

Current catch table on the train split (fault type x real built designs):
{table}

TARGET: {tid} - {title}
{history}
Write ONE new file fc/gx/rules/{fname}.py with an @gx_rule('{rid}', ...) check(g) that yields
Finding('{rid}', 'error', msg, part.key) and catches this kind of defect for the right PHYSICAL reason, stated generally
(a real workshop limit with a concrete threshold and a docstring saying why) - not a fingerprint of how the mutation
was coded. The same rule should catch real files with that defect, not only the seeded ones.
Hard constraints (an automatic gate checks them, the rule is thrown away otherwise):
  * zero errors on every built design in the good_train split (they were cut and assembled by real people:
    if your rule flags one, your threshold or reasoning is wrong),
  * no crashes on any corpus file (wrap nothing silently; just write robust code),
  * it must not make other fault types less caught, and must not flag much more of the anonymous noise corpus.
Tools: `GX_K=6 python3 -m fc.gx.score` (quick, ~2 min), `python3 -m fc.gx.score --show {tid}` (missed mutants and what
rules say), `python3 -m fc.gx.score --fp` (flagged good designs). In Python: `from fc.gx import corpus;
gs = list(corpus.designs('good_train'))` gives the built designs (parsed, cached).
Do NOT edit other rules, fault files, model.py, corpus.py or score.py. Another loop works on the kommode checker in this
repo: do not touch or read fc/rules/, faults/heldout*.py, faults/retired*.py, faults/variants.py, loop.py.
Do NOT open faults/gx_heldout.py or anything
under corpus/raw except through fc.gx.model. Never execute files from corpus/raw. Finish with a one-line summary."""

MINE = """You are the fault MINER for a checker of CNC-cut flat-pack furniture files from any designer (this directory).
Read fc/gx/model.py, fc/gx/mutate.py, faults/gx_train.py, faults/gx_mined.py (if it exists), docs/rules-from-manuals.md and
docs/tools-and-rules.md. Do NOT open fc/gx/rules/ or faults/gx_heldout.py (nor the other loop's faults/heldout*.py, retired*.py, variants.py).
Add {n} NEW fault types to faults/gx_mined.py (create it like faults/gx_train.py with FAULTS = [...]; keep existing
entries; ids gm01, gm02, ... continuing). Each must be a real, documented way CNC plywood / flat-pack furniture fails
(manufacturer guides, CNC forum failure stories, Opendesk/WikiHouse design guides, hardware mounting instructions,
machining limits) with source=, clearly defective, and NOT a variant of an existing type. Each fn(g, rng) returns a
mutated clone(g) or None; it must apply to at least 5 designs of `list(fc.gx.corpus.designs('good_train'))` - check it
with a small script (cwd = repo). Never execute files from corpus/raw. Finish with the new ids and titles."""


def next_rid():
    ns = [int(f[1:3]) for f in os.listdir(RULES) if f.startswith('g') and f[1:3].isdigit()]
    return max(ns + [0]) + 1


def mine(n=3):
    before = open(MINED).read() if os.path.exists(MINED) else None
    out = agent(MINE.format(n=n))
    try:
        r = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0,"."); import faults.gx_mined as m; print(len(m.FAULTS))'],
                           cwd=HERE, capture_output=True, text=True, timeout=120)
        ok = r.returncode == 0
    except Exception:
        ok = False
    if not ok:
        if before is None:
            os.path.exists(MINED) and os.remove(MINED)
        else:
            open(MINED, 'w').write(before)
    else:
        commit('loop: miner added fault types')
    log(dict(step='mine', ok=ok, agent=out[-300:]))


OWN = ['fc/gx', 'gx_gate.py', 'faults/gx_train.py', 'faults/gx_mined.py', 'loop_gx.py', 'gx_score_history.jsonl', 'gx_loop_log.jsonl',
       'corpus/README.md', 'corpus/good_exclusions.json']


def commit(msg):
    """Commit ONLY the loop's own files (other sessions may have work staged in this repo)."""
    paths = [p for p in OWN if os.path.exists(os.path.join(HERE, p))]
    subprocess.run(['git', 'add', '--'] + paths, cwd=HERE)
    subprocess.run(['git', '-c', 'user.name=rsi-loop', '-c', 'user.email=noreply@local', 'commit', '-qm', msg, '--'] + paths, cwd=HERE)


def gate(before, after, tid):
    tb, ta = before['train']['types'], after['train']['types']
    why = []
    if ta.get(tid, {}).get('caught', 0) <= tb.get(tid, {}).get('caught', 0): why.append('target not caught more often')
    lost = [k for k in tb if k in ta and ta[k]['caught'] < tb[k]['caught']]
    if lost: why.append('regression on %s' % lost)
    if after['fp']['train'] > before['fp']['train']:
        why.append('false alarms on built designs: %s' % [x for x in after['fp']['train_ids'] if x not in before['fp']['train_ids']][:5])
    cb = sum(before['noise']['crashes'].values()); ca = sum(after['noise']['crashes'].values())
    if ca > cb: why.append('rule crashes on %d corpus files' % (ca - cb))
    if after['noise']['flag_rate'] > before['noise']['flag_rate'] + 0.03:
        why.append('noise flag rate %.0f%% -> %.0f%%' % (100 * before['noise']['flag_rate'], 100 * after['noise']['flag_rate']))
    return why


def main():
    hours, iters = arg('--hours', None, float), arg('--iters', None, int)
    mine_every, max_tries = arg('--mine-every', 3, int), arg('--max-tries', 2, int)
    deadline = time.time() + hours * 3600 if hours else None
    tries, reasons, step = {}, {}, 0
    cur = snapshot()
    subprocess.run([sys.executable, '-m', 'fc.gx.score', '--log', 'loop start'], cwd=HERE, capture_output=True)
    log(dict(step='start', train=cur['train']['macro'], transfer=cur['transfer']['macro'], heldout=cur['heldout']['macro'], fp=cur['fp']))
    while True:
        if deadline and time.time() > deadline: break
        if iters is not None and step >= iters: break
        if mine_every and step % mine_every == 0 and step > 0 or (mine_every and not os.path.exists(MINED)):
            mine(); cur = snapshot()
        cand = [(v['caught'] / v['n'], k, v) for k, v in cur['train']['types'].items()
                if v['n'] and v['caught'] < v['n'] and tries.get(k, 0) < max_tries]
        if not cand:
            if mine_every:
                mine(); cur = snapshot(); tries = {}
                if not [k for k, v in cur['train']['types'].items() if v['caught'] < v['n']]: break
                continue
            break
        _, tid, v = min(cand)
        tries[tid] = tries.get(tid, 0) + 1; step += 1
        rid = 'G%02d' % next_rid(); fname = 'g%02d_auto_%s' % (next_rid(), tid)
        path = os.path.join(RULES, fname + '.py')
        hist = ('Previous attempts at this target were REJECTED by the gate: %s' % '; '.join(reasons.get(tid, []))) if reasons.get(tid) else ''
        t0 = time.time()
        out = agent(WRITE.format(table=table(cur), tid=tid, title=v['title'], fname=fname, rid=rid, history=hist))
        if not os.path.exists(path):
            reasons.setdefault(tid, []).append('no rule file was written')
            log(dict(step='write', target=tid, result='no file', agent=out[-300:])); continue
        new = snapshot()
        why = gate(cur, new, tid)
        if why:
            shutil.move(path, path + '.rejected'); reasons.setdefault(tid, []).append(' & '.join(why))
            log(dict(step='write', target=tid, rule=fname, accepted=False, why=why, secs=round(time.time() - t0)))
        else:
            subprocess.run([sys.executable, '-m', 'fc.gx.score', '--log', 'loop: %s for %s' % (fname, tid)], cwd=HERE, capture_output=True)
            commit('loop: accept %s (%s %d->%d)' % (fname, tid, cur['train']['types'][tid]['caught'], new['train']['types'][tid]['caught']))
            log(dict(step='write', target=tid, rule=fname, accepted=True, train=new['train']['macro'], transfer=new['transfer']['macro'],
                     heldout=new['heldout']['macro'], fp_heldout=new['fp']['heldout'], secs=round(time.time() - t0)))
            cur = new
    log(dict(step='end', train=cur['train']['macro'], transfer=cur['transfer']['macro'], heldout=cur['heldout']['macro'], fp=cur['fp']['n']))


if __name__ == '__main__':
    main()
