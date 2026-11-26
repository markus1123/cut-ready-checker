#!/usr/bin/env python3
"""The loop_gx.py gate as a command, for running the loop from INSIDE one agent session (e.g. a cloud routine,
where the agent itself writes rules instead of spawning `claude -p`). The agent must not edit this file.

    python3 gx_gate.py status                 # catch table + the targets to work on (lowest catch first)
    python3 gx_gate.py check fc/gx/rules/gNN_auto_<target>.py <target>
                                              # gate a new rule: accept -> git commit, reject -> .rejected + reasons
    python3 gx_gate.py mined                  # after adding fault types to faults/gx_mined.py: validate + commit
    python3 gx_gate.py refine fc/gx/rules/<existing rule>.py
                                              # gate an edit that makes ONE existing rule more precise: accept when that
                                              # rule flags >= 3 fewer noise designs, the noise flag rate does not rise,
                                              # no train or transfer fault type loses a catch, no new false alarm or crash.
                                              # Reject -> the file is restored and the reasons are logged.

A check scores everything once (~5-15 min with all cores; GX_JOBS=N to limit). Run it detached so a tool time limit
cannot kill it between accepting and committing:  nohup python3 gx_gate.py check ... > gate.out 2>&1 &

State (the last accepted score) is kept in .gxwork/state.json; logs go to gx_loop_log.jsonl.
"""
import json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loop_gx as L  # noqa: E402

STATE = os.path.join(HERE, '.gxwork', 'state.json')


def state(refresh=False):
    if not refresh and os.path.exists(STATE):
        return json.load(open(STATE))
    s = L.snapshot()
    os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(s, open(STATE, 'w'))
    return s


def main():
    a = sys.argv[1:]
    if not a or a[0] == 'status':
        s = state('--refresh' in a)
        print('train %.3f  transfer %.3f  false alarms (train) %d  noise flag %.0f%%  rules %d' % (
            s['train']['macro'], s['transfer']['macro'], s['fp']['train'], 100 * s['noise']['flag_rate'], len(s['rules'])))
        print(L.table(s))
        todo = sorted((v['caught'] / v['n'], k) for k, v in s['train']['types'].items() if v['n'] and v['caught'] < v['n'])
        print('targets, lowest first:', ', '.join(k for _, k in todo))
        br = s['noise'].get('by_rule')
        if br: print('noise designs flagged per rule (refine targets, highest first):', ', '.join(
            '%s %d' % kv for kv in sorted(br.items(), key=lambda kv: -kv[1]) if kv[1]))
        return
    if a[0] == 'check':
        path, tid = os.path.join(HERE, a[1]), a[2]
        before = state(); after = L.snapshot()
        why = L.gate(before, after, tid)
        name = os.path.basename(path)[:-3]
        if why:
            shutil.move(path, path + '.rejected')
            L.log(dict(step='write', where='session', target=tid, rule=name, accepted=False, why=why))
            print('REJECTED:', '; '.join(why)); sys.exit(1)
        json.dump(after, open(STATE, 'w'))
        from fc.gx.score import history
        history(after, 'session: %s for %s' % (name, tid))
        L.log(dict(step='write', where='session', target=tid, rule=name, accepted=True, train=after['train']['macro'],
                   transfer=after['transfer']['macro']))
        L.commit('loop: accept %s (%s %d->%d)' % (name, tid, before['train']['types'].get(tid, {}).get('caught', 0),
                                                  after['train']['types'][tid]['caught']))
        print('ACCEPTED. train %.3f -> %.3f' % (before['train']['macro'], after['train']['macro']))
        return
    if a[0] == 'refine':
        rel = a[1]; path = os.path.join(HERE, rel)
        changed = subprocess.run(['git', 'diff', '--name-only', 'HEAD'], cwd=HERE, capture_output=True, text=True).stdout.split()
        untracked = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard', 'fc/gx', 'faults'], cwd=HERE,
                                   capture_output=True, text=True).stdout.split()
        if changed != [rel] or untracked:
            print('refine needs exactly one modified, already committed rule file and nothing else changed; got %s %s'
                  % (changed, untracked)); sys.exit(1)
        before = state(); after = L.snapshot()

        src = open(path).read()
        import re
        m = re.search(r"@(?:gx_)?rule\(\s*'(\w+)'", src)
        rid = m.group(1) if m else None
        why = []
        if not rid or rid not in before['rules']: why.append('could not find the rule id of %s in the current rules' % rel)
        else:
            nb, na = before['noise'].get('by_rule', {}).get(rid), after['noise']['by_rule'].get(rid, 0)
            if nb is None: why.append('state has no per-rule noise counts; run: python3 gx_gate.py status --refresh')
            elif na > nb - 3: why.append('%s flags %d noise designs, was %d (need at least 3 fewer)' % (rid, na, nb))
        if after['noise']['flag_rate'] > before['noise']['flag_rate']:
            why.append('noise flag rate rose %.1f%% -> %.1f%%' % (100 * before['noise']['flag_rate'], 100 * after['noise']['flag_rate']))
        for s_ in ('train', 'transfer'):
            tb, ta = before[s_]['types'], after[s_]['types']
            lost = [k for k in tb if k in ta and ta[k]['caught'] < tb[k]['caught']]
            if lost: why.append('%s catches lost on %s' % (s_, lost))
        if after['fp']['n'] > before['fp']['n']: why.append('false alarms on built designs %d -> %d' % (before['fp']['n'], after['fp']['n']))
        if sum(after['noise']['crashes'].values()) > sum(before['noise']['crashes'].values()): why.append('new rule crashes')
        if why:
            shutil.copy(path, path[:-3] + '.refine-rejected')
            subprocess.run(['git', 'checkout', '--', rel], cwd=HERE)
            L.log(dict(step='refine', where='session', rule=rid, file=rel, accepted=False, why=why))
            print('REJECTED:', '; '.join(why), '(attempt kept as %s.refine-rejected, file restored)' % rel[:-3]); sys.exit(1)
        json.dump(after, open(STATE, 'w'))
        from fc.gx.score import history
        history(after, 'session: refine %s' % rid)
        L.log(dict(step='refine', where='session', rule=rid, file=rel, accepted=True,
                   noise_rule=[before['noise']['by_rule'][rid], after['noise']['by_rule'][rid]],
                   noise_flag=[before['noise']['flag_rate'], after['noise']['flag_rate']]))
        L.commit('loop: refine %s (noise designs %d->%d, flag rate %.1f%%->%.1f%%)' % (
            rid, before['noise']['by_rule'][rid], after['noise']['by_rule'][rid],
            100 * before['noise']['flag_rate'], 100 * after['noise']['flag_rate']))
        print('ACCEPTED. %s noise designs %d -> %d, flag rate %.1f%% -> %.1f%%' % (
            rid, before['noise']['by_rule'][rid], after['noise']['by_rule'][rid],
            100 * before['noise']['flag_rate'], 100 * after['noise']['flag_rate']))
        return
    if a[0] == 'mined':
        r = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0,"."); import faults.gx_mined as m; print(len(m.FAULTS))'],
                           cwd=HERE, capture_output=True, text=True)
        if r.returncode:
            print('faults/gx_mined.py does not import:\n' + r.stderr[-1500:]); sys.exit(1)
        s = state(refresh=True)
        low = [k for k, v in s['train']['types'].items() if k.startswith('gm') and v['n'] < 5]
        if low:
            print('these types apply to fewer than 5 good_train designs, fix or remove them:', low); sys.exit(1)
        L.log(dict(step='mine', where='session', ok=True, types=len(s['train']['types'])))
        L.commit('loop: miner added fault types')
        print('OK: %d fault types' % len(s['train']['types']))


if __name__ == '__main__':
    main()
