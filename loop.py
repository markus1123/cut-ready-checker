#!/usr/bin/env python3
"""Recursive self-improvement loop for the checker (v2).

    python3 loop.py --mine 6          # miner: an agent writes 6 new realistic faults into faults/mined.py
    python3 loop.py --write 5         # writer: up to 5 rules, each aimed at a FAMILY of currently missed practice faults
    python3 loop.py --round           # one full round: retire the used-up unseen test, write rules on everything missed,
                                      #   have a fresh red-team agent write a new unseen test, score it blind once
    python3 loop.py --round --write 8 # same, with 8 writer attempts
    (--iters N is kept as an alias of --write N)

Practice = train + mined + retired (old unseen tests) + variants. The unseen test (faults/heldout.py) is never shown to
the writer, the miner or the variant agent; its titles are hidden from score output until after the blind score.

Gate for a new rule (plain code, never an LLM opinion at check time):
  1. catches at least one fault it was aimed at,
  2. every fault caught before is still caught (no regression),
  3. zero errors on the known-good designs (faults/good.py),
  4. GENERAL: it also catches another practice fault it was not written for, or at least 2 of 3 variants of its
     target that a separate agent writes without seeing the rule. A rule that only catches its own example is
     rejected as too narrow; the writer gets one retry with that feedback.
Every decision is logged in loop_log.jsonl; accepted rules are committed by author `rsi-loop`.
"""
import glob, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
CLAUDE = os.environ.get('CLAUDE_BIN', 'claude')
MODEL = os.environ.get('FC_MODEL', '')
PRACTICE = ('train', 'mined', 'retired', 'variants')
N_VARIANTS = 3


def agent(prompt, tools='Read,Write,Edit,Bash,Glob,Grep'):
    cmd = [CLAUDE, '-p', prompt, '--allowedTools', tools, '--permission-mode', 'acceptEdits']
    if MODEL:
        cmd += ['--model', MODEL]
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, timeout=1500, stdin=subprocess.DEVNULL)
    return r.stdout[-2000:]


def evaluate(sets):
    # fresh process: newly written / rejected rule modules must not linger in the registry
    code = ('import json,sys; sys.path.insert(0,"."); from fc import score; '
            'print(json.dumps(score.evaluate(%r, verbose=False)))' % (list(sets),))
    out = subprocess.run([sys.executable, '-c', code], cwd=HERE, capture_output=True, text=True)
    return json.loads(out.stdout.strip().split('\n')[-1])


def snapshot():
    res = evaluate(list(PRACTICE) + ['good'])
    rows = [r for n in PRACTICE for r in res.get(n, [])]
    caught = {r['id'] for r in rows if r['caught']}
    missed = [r for r in rows if not r['caught']]
    fp = [r['id'] for r in res['good'] if r['caught']]
    return caught, missed, fp


def set_of(fid):
    return {'m': 'mined', 'v': 'variants', 't': 'train'}.get(fid[0], 'retired')


RULE_BRIEF = """You are improving a DFM checker for CNC-cut flat-pack furniture (repo: this directory; read README.md,
fc/core.py, fc/design.py, fc/world.py, fc/geom.py and 3-4 existing rules in fc/rules/ first, especially the general ones
r27_general_geometry.py and r32_file_readback.py). The generator that is checked lives in ../kommode-bestilling/generator
(kommode.py, nestlib.py) - read but DO NOT modify it.

The checker currently MISSES these practice faults (id - title):
{missed}
Inspect any of them with `python3 -m fc.score --show <id>` (shows every layer's verdict and writes the files to .work/<id>).

Pick ONE shared physical cause behind as many of them as possible and write ONE new rule file fc/rules/{fname}.py
(@rule id {rid}) that checks that cause in general - a class of mistake, not the example. A rule that only matches one
fault's exact numbers will be REJECTED: the gate also tests it on other faults and on variants written by another
agent who has not seen your rule. Use concrete thresholds with the reason (manufacturer data, workshop practice) in the
docstring. It must NOT error on faults/good.py (check with `python3 -m fc.score`). Do not edit other rules, faults,
the generator or the scoring code. Do not open faults/heldout.py or faults/variants.py.
Finish with one line: TARGETS: <comma-separated ids you aimed at>.{feedback}"""

VARIANT_BRIEF = """You write test variants for a CNC flat-pack furniture checker (this directory; read fc/core.py, fc/design.py,
faults/helpers.py and the generator ../kommode-bestilling/generator/kommode.py). Do NOT open fc/rules/, faults/heldout.py
or faults/good.py.

For each of these faults, write {n} VARIANTS: the same kind of mistake with a different magnitude, a different part,
or a different place in the design - not a copy. Faults (set: file):
{targets}
Append them to faults/variants.py (keep existing entries) as Fault objects with ids v_<faultid>_<k> (k = 1..{n}),
a title, why, and the same kind of hook (params/parts/dxf) as the original. Each must be a genuine defect that must
not be cut. Check them with `python3 -m fc.validate_faults variants` - every one must print `ok` (not crash or inert).
Finish with the list of ids."""

RED_BRIEF = """You are a red-team author writing a fresh, blind test set for a CNC furniture checker you must NOT look at.
The generator is ../kommode-bestilling/generator/kommode.py (with nestlib.py, params.json, beslag/skinne.json): an
8-drawer chest; parts A top, B bottom, C/CH sides, D middle wall, H plinth, K fronts, S/SH drawer sides, E1/E2 drawer
ends, SB drawer bottom, G back panel; asm also has BEIN (legs) and SKINNE (slides). A fault is a Fault (fc/core.py) with
params(P, S), parts(parts, asm, info) or dxf(files) hooks; fc/design.py shows how it is applied; faults/helpers.py helps.

Write faults/heldout_next.py with FAULTS = 25 faults, ids {prefix}01..{prefix}25, about 1/3 each hook type, each a
realistic, serious way a flat-pack CNC job goes wrong (wasted sheet, part that cannot be assembled, broken bit, unsafe),
with title, why and source. These failure modes are already covered - write DIFFERENT ones: {titles_file}.
No hard-coded values that may change. Validate with `python3 -m fc.validate_faults heldout_next` until 25/25 ok.
STRICTLY FORBIDDEN: opening or listing fc/rules/, fc/world.py, fc/geom.py, fc/score.py, fc/attribution.py, faults/
(except helpers.py and your own file), attribution.json, score_history.jsonl, loop_log.jsonl, loop.py, docs/, demo/,
site/, README.md or git history; running fc.score or fc.attribution. Edit only faults/heldout_next.py.
Finish with the 25 titles."""


def next_rid():
    # one file may register several rule ids (e.g. r27_general_geometry.py has R27-R31): use the registered ids
    ids = []
    for f in glob.glob(os.path.join(HERE, 'fc', 'rules', 'r*.py*')):
        ids += [int(x) for x in re.findall(r"@rule\(\s*'R(\d+)'", open(f, encoding='utf-8').read())]
    return max(ids) + 1


def log(entry):
    entry['t'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    with open(os.path.join(HERE, 'loop_log.jsonl'), 'a') as f:
        f.write(json.dumps(entry) + '\n')
    print(json.dumps({k: v for k, v in entry.items() if k != 'agent'}))


def commit(msg):
    # only this loop's own files: another loop (loop_gx.py) may be working in the same repo
    paths = glob.glob(os.path.join(HERE, 'fc', 'rules', 'r*_auto.py')) + glob.glob(os.path.join(HERE, 'faults', 'retired*.py')) + \
        [os.path.join(HERE, p) for p in ('faults/heldout.py', 'faults/variants.py', 'loop_log.jsonl', 'score_history.jsonl')]
    subprocess.run(['git', 'add', '-A', '--'] + [p for p in paths if os.path.exists(p)] + ['faults/heldout.py'], cwd=HERE)
    subprocess.run(['git', '-c', 'user.name=rsi-loop', '-c', 'user.email=noreply@local', 'commit', '-qm', msg], cwd=HERE)


def score_log(note):
    subprocess.run([sys.executable, '-m', 'fc.score', '--log', note], cwd=HERE, capture_output=True)


def variants_caught(rule_path, targets):
    """Ask a blind agent for variants of the targets, then count how many the checker (with the new rule) catches."""
    have = {r['id'] for r in evaluate(['variants'])['variants']}
    need = [t for t in targets if not any(v.startswith('v_%s_' % t['id']) for v in have)]
    if need:
        hidden = rule_path + '.hidden'
        os.rename(rule_path, hidden)                    # the variant agent must not be able to read the rule
        try:
            agent(VARIANT_BRIEF.format(n=N_VARIANTS, targets='\n'.join('  %s (%s): %s' % (t['id'], set_of(t['id']), t['title']) for t in need)))
        finally:
            os.rename(hidden, rule_path)
    rows = evaluate(['variants'])['variants']
    mine = [r for r in rows if any(r['id'].startswith('v_%s_' % t['id']) for t in targets)]
    return sum(r['caught'] for r in mine), len(mine), [r['title'] for r in mine if not r['caught']]


def write_rules(n):
    tried_empty = 0
    for _ in range(n):
        caught, missed, fp = snapshot()
        if not missed:
            print('nothing left to fix'); return
        rid = next_rid(); fname = 'r%02d_auto' % rid
        path = os.path.join(HERE, 'fc', 'rules', fname + '.py')
        listing = '\n'.join('  %s - %s' % (m['id'], m['title']) for m in missed[:40])
        feedback = ''
        for attempt in (1, 2):
            out = agent(RULE_BRIEF.format(missed=listing, fname=fname, rid='R%02d' % rid, feedback=feedback))
            if not os.path.exists(path):
                log(dict(step='write', result='no file written', attempt=attempt, agent=out[-300:])); break
            caught2, _, fp2 = snapshot()
            new = caught2 - caught
            m = re.search(r'TARGETS:\s*(.+)', out)
            aimed = {x.strip() for x in m.group(1).split(',')} if m else set()
            hit = new & aimed if aimed else new
            other = sorted(new - aimed) if aimed else sorted(new)[1:]
            base_ok = bool(new) and caught <= caught2 and not fp2
            v_c = v_n = 0; v_miss = []
            if base_ok and not other:
                targets = [x for x in missed if x['id'] in (hit or new)][:3]
                v_c, v_n, v_miss = variants_caught(path, targets)
            general = bool(other) or bool(v_n and v_c >= max(2, (2 * v_n + 2) // 3))
            ok = base_ok and general
            log(dict(step='write', rule=fname, attempt=attempt, accepted=ok, aimed=sorted(aimed), caught_new=sorted(new),
                     also_caught=other, variants=[v_c, v_n], lost=sorted(caught - caught2), false_alarms=fp2,
                     reason=None if ok else ('regression' if caught - caught2 else 'false alarm' if fp2 else
                                             'catches nothing' if not new else 'too narrow'),
                     agent=out[-300:]))
            if ok:
                score_log('loop: %s (+%d practice, variants %d/%d)' % (fname, len(new), v_c, v_n))
                commit('loop: accept %s (catches %s)' % (fname, ', '.join(sorted(new))))
                break
            if base_ok and attempt == 1:                # narrow but correct: one retry with concrete feedback
                feedback = ('\n\nYOUR PREVIOUS RULE (%s, still in place - edit it) caught %s but was REJECTED AS TOO NARROW: '
                            'it caught %d of %d variants written by another agent. Variants it missed:\n%s\n'
                            'Generalise the check to the underlying cause.' % (fname, ', '.join(sorted(new)), v_c, v_n,
                                                                              '\n'.join('  - ' + t for t in v_miss)))
                continue
            os.rename(path, path + '.rejected')
            break


def retire_current():
    """Move the current unseen test (already scored blind once) into practice. Returns its version (0 if none)."""
    fdir = os.path.join(HERE, 'faults')
    cur = os.path.join(fdir, 'heldout.py')
    if not os.path.exists(cur):
        return 0
    m = re.search(r'^VERSION\s*=\s*(\d+)', open(cur).read(), re.M)
    ver = int(m.group(1)) if m else 1
    shutil.move(cur, os.path.join(fdir, 'retired_v%d.py' % ver))
    log(dict(step='retire', version=ver))
    return ver


def new_test(ver):
    """A fresh red-team agent writes unseen test v(ver+1); it is validated and scored blind once."""
    fdir = os.path.join(HERE, 'faults')
    cur = os.path.join(fdir, 'heldout.py')
    titles = os.path.join(HERE, '.work', 'existing_titles.txt')
    os.makedirs(os.path.dirname(titles), exist_ok=True)
    code = ('import sys; sys.path.insert(0,"."); from fc.score import load_set\n'
            'for n in ("train","mined","retired","variants"):\n    [print("-", f.title) for f in load_set(n)]')
    open(titles, 'w').write(subprocess.run([sys.executable, '-c', code], cwd=HERE, capture_output=True, text=True).stdout)
    prefix = 'h%d_' % (ver + 1)                     # fresh id prefix per round (h4_01, ...)
    out = agent(RED_BRIEF.format(prefix=prefix, titles_file=titles))
    nxt = os.path.join(fdir, 'heldout_next.py')
    if not os.path.exists(nxt):
        log(dict(step='red-team', result='no file written', agent=out[-300:])); return False
    val = subprocess.run([sys.executable, '-m', 'fc.validate_faults', 'heldout_next'], cwd=HERE, capture_output=True, text=True).stdout
    if not val.strip().endswith('0 problems'):
        log(dict(step='red-team', result='invalid faults', validator=val[-400:])); return False
    open(nxt, 'a').write('\nVERSION = %d   # written blind by the red-team agent in loop round %d\n' % (ver + 1, ver + 1))
    shutil.move(nxt, cur)
    score_log('round %d: new blind unseen test v%d' % (ver + 1, ver + 1))
    last = json.loads(open(os.path.join(HERE, 'score_history.jsonl')).read().strip().split('\n')[-1])
    log(dict(step='blind-score', version=ver + 1, caught=last.get('heldout_caught'), n=last.get('heldout_n'),
             false_alarms=last.get('false_pos'), rules=last.get('rules')))
    commit('loop: round %d - retire test v%d, blind score on new test v%d: %s/%s'
           % (ver + 1, ver, ver + 1, last.get('heldout_caught'), last.get('heldout_n')))
    return True


def main():
    a = sys.argv[1:]
    n = lambda k: int(a[a.index(k) + 1]) if k in a else 0
    if '--mine' in a:
        log(dict(step='mine', n=n('--mine'), agent=agent(MINE_BRIEF.format(n=n('--mine')))[-400:]))
    writes = n('--write') or n('--iters') or (6 if '--round' in a else 0)
    ver = retire_current() if '--round' in a else None
    write_rules(writes)
    if '--round' in a:
        new_test(ver)

MINE_BRIEF = """You are the fault MINER for a CNC flat-pack furniture checker (this directory; read README.md, fc/design.py,
fc/core.py, faults/train.py and faults/helpers.py; the generator is ../kommode-bestilling/generator/kommode.py).
Do not open faults/heldout.py or fc/rules/.
Add {n} NEW faults to faults/mined.py (keep existing entries; ids m01, m02, ... continuing). Each must be a real,
documented way flat-pack/CNC/cabinet jobs fail - Blum/Hettich mounting instructions, Minifix/dowel spacing, ShopBot/
VCarve forum failure stories, edge-banding and grain rules, hold-down, tool reach, assembly access - NOT a copy of an
existing fault. Put the source in source=. Each must change the generated output (check with
`python3 -m fc.validate_faults mined`) and be a genuine defect. Finish with the list of ids and titles."""


if __name__ == '__main__':
    main()
