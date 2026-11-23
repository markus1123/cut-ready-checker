"""Which layer catches which fault: generator check and every rule, run separately on every fault.

    python3 -m fc.attribution        # writes attribution.json (used by demo/build.py)
"""
import json, os, sys
from . import design
from .core import gen_errors, run_rules, load_rules
from .score import load_set, HERE

SETS = ['train', 'mined', 'retired', 'heldout', 'good']


def main():
    rules = load_rules()
    rows = []
    for name in SETS:
        for f in load_set(name):
            d = design.make(fault=f)
            try:
                g = bool(gen_errors(d))
                hit = sorted({x.rule for x in run_rules(d) if x.severity in ('error', 'crash')})
            finally:
                design.cleanup(d)
            rows.append(dict(id=f.id, set=name, title=f.title, why=f.why, source=f.source, gen=g, rules=hit))
            print('%-4s %-8s gen=%d %s' % (f.id, name, g, ','.join(hit)), file=sys.stderr)
    out = dict(rules=sorted(rules), rows=rows)
    json.dump(out, open(os.path.join(HERE, 'attribution.json'), 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
