#!/usr/bin/env python3
"""The loop_gx.py gate as a command, for running the loop from INSIDE one agent session (e.g. a cloud routine,
where the agent itself writes rules instead of spawning `claude -p`). The agent must not edit this file.

    python3 gx_gate.py status                 # catch table + the targets to work on (lowest catch first)
    python3 gx_gate.py check fc/gx/rules/gNN_auto_<target>.py <target>
                                              # gate a new rule: accept -> git commit, reject -> .rejected + reasons
    python3 gx_gate.py mined                  # after adding fault types to faults/gx_mined.py: validate + commit

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
