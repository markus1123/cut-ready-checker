#!/usr/bin/env python3
"""Cost optimizer: hill climbing with random restarts over the hidden material choices, number of columns and
nesting effort. Every candidate must pass the full checker (generator check + all rules) or it is rejected.

    python3 optimize.py                 # keep the look (front/ytre) fixed
    python3 optimize.py --free-look     # also let fronts/top/sides change
    python3 optimize.py --region bay_area   # swap in regions/bay_area.json (USD, sales tax, local rates)
Writes optimize_history.jsonl (one line per evaluation) and optimize_result.json.
Cost = whole sheets x price + spindle time x 568 kr/h x 1.5 (real time vs formula) + hardware per drawer.
Prices marked ~ in materialer.json are ESTIMATES.
"""
import copy, json, os, random, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fc import design  # noqa: E402
from fc.core import verdict, run_rules  # noqa: E402
import kommode, nestlib  # noqa: E402

KR_PER_H = 568.0
TIME_FACTOR = 1.5           # feed x length formula underestimates real spindle time (plunges, accel)
HW_PER_DRAWER = 320.0       # ~ slide pair 250 + handle 50 + screws 20 (ESTIMATE)
HW_PER_WALL = 120.0         # Minifix + dowels for one middle wall (ESTIMATE)
NEST_TRIES = 40             # random part orders tried per material on top of the 5 greedy orders

_orig_pack = nestlib.pack


def pack(items, sizes, rot, margin, gap):
    """Greedy orders + seeded random orders; keep the one that uses the fewest sheet pieces."""
    best = None
    try:
        best = _orig_pack(items, sizes, rot, margin, gap)
    except nestlib.DoesNotFit:
        pass
    rnd = random.Random(len(items))
    for _ in range(NEST_TRIES):
        it = items[:]; rnd.shuffle(it)
        try:
            bins = [b for b in nestlib._pack1(it, sizes, rot, margin, gap) if b.placed]
        except nestlib.DoesNotFit:
            continue
        key = lambda bs: (max(b.idx for b in bs), len(bs))
        if best is None or key(bins) < key(best):
            best = bins
    if best is None:
        raise nestlib.DoesNotFit('no order fits')
    return best


TAX = 0.0                   # Norwegian prices already include mva
CURRENCY = 'NOK'


def load_raw(region=None):
    global KR_PER_H, HW_PER_DRAWER, HW_PER_WALL, TAX, CURRENCY
    P = json.load(open(os.path.join(design.GEN, 'params.json'), encoding='utf-8'))
    C = json.load(open(os.path.join(design.GEN, 'materialer.json'), encoding='utf-8'))
    S = json.load(open(os.path.join(design.GEN, P['skinne']), encoding='utf-8'))
    if region:
        R = json.load(open(os.path.join(HERE, 'regions', region + '.json'), encoding='utf-8'))
        C = dict(C, materialer=R['materialer'])
        P['materialvalg'].update(R['start'])
        KR_PER_H, HW_PER_DRAWER, HW_PER_WALL = R['machine_per_h'], R['hw_per_drawer'], R['hw_per_wall']
        TAX, CURRENCY = R['sales_tax'], R['currency']
    return P, C, S


def candidate_space(C, free_look):
    roles = ['korpus', 'skuff', 'skuffebunn', 'bakplate'] + (['front', 'ytre'] if free_look else [])
    space = {r: [m['id'] for m in C['materialer'] if r in m['roller']] for r in roles}
    space['kolonner'] = [2, 3]
    return space


CACHE = {}


def evaluate(x, P0, C0, S0, strict_width):
    key = json.dumps(x, sort_keys=True) + str(strict_width)
    if key in CACHE:
        return CACHE[key]
    P, C, S = copy.deepcopy(P0), copy.deepcopy(C0), copy.deepcopy(S0)
    for r, v in x.items():
        if r == 'kolonner':
            P['kolonner'] = v
        else:
            P['materialvalg'][r] = v
    for m in C['materialer']:                      # assume boards measure as nominal for the comparison
        m['tykkelse_malt'] = m['tykkelse_malt'] or m['tykkelse']
        m['pris'] = m['pris'] if m['pris'] is not None else m['pris_anslag']
    P = kommode.resolve(P, C)
    P['verksted']['bekreftet'] = True
    S.update(copy.deepcopy(design.READY_SLIDE))
    res = dict(x=x, ok=False, cost=None)
    try:
        d = design.make(P, S)
    except Exception as e:
        res['why'] = 'generator: %s' % e
        CACHE[key] = res; return res
    try:
        caught, msgs = verdict(d)
        warns = [f.msg for f in run_rules(d) if f.severity == 'warn' and f.rule == 'R18']
        if strict_width and warns:
            caught, msgs = True, msgs + warns
        sheets = sum(c['sum'] for c in d.summary['materialkost']) * (1 + TAX)
        mins = sum(s['min'] for s in d.summary['plater']) * TIME_FACTOR
        drawers = P['rader'] * P['kolonner']
        hw = (drawers * HW_PER_DRAWER + (P['kolonner'] - 1) * HW_PER_WALL) * (1 + TAX)
        cost = sheets + mins / 60 * KR_PER_H + hw
        res.update(ok=not caught, why=msgs[:3], cost=round(cost), sheets=round(sheets), cnc_min=round(mins),
                   cnc_kr=round(mins / 60 * KR_PER_H), hardware=round(hw), drawers=drawers,
                   box_width=round(d.info['bw']), estimate=any(c['anslag'] for c in d.summary['materialkost']),
                   materials=[dict(navn=c['navn'], ark=c['ark'], kr=round(c['sum'] * (1 + TAX)), used=c['utnyttelse'], roles=c['roller'])
                              for c in d.summary['materialkost']])
    finally:
        design.cleanup(d)
    CACHE[key] = res
    return res


def climb(P0, C0, S0, space, start, strict_width, log, restarts=3, seed=7):
    rnd = random.Random(seed)
    best_overall = None
    n = 0

    def ev(x):
        nonlocal n, best_overall
        r = evaluate(x, P0, C0, S0, strict_width); n += 1
        if r['ok'] and (best_overall is None or r['cost'] < best_overall['cost']):
            best_overall = r
        log.write(json.dumps(dict(n=n, strict=strict_width, cost=r['cost'], ok=r['ok'],
                                  best=best_overall['cost'] if best_overall else None, x=x)) + '\n'); log.flush()
        return r

    for rs in range(restarts + 1):
        x = dict(start) if rs == 0 else {k: rnd.choice(v) for k, v in space.items()}
        cur = ev(x)
        improved = True
        while improved:
            improved = False
            moves = [(k, v) for k, vals in space.items() for v in vals if v != x[k]]
            rnd.shuffle(moves)
            for k, v in moves:                       # first-improvement hill climbing
                y = dict(x, **{k: v})
                r = ev(y)
                if r['ok'] and (not cur['ok'] or r['cost'] < cur['cost']):
                    x, cur, improved = y, r, True
                    print(('  [%s] %5d '+CURRENCY+'  %s=%s') % ('strict' if strict_width else 'loose', r['cost'], k, v))
                    break
    return best_overall, n


def main():
    a = sys.argv[1:]
    free = '--free-look' in a
    region = a[a.index('--region') + 1] if '--region' in a else None
    suf = '_' + region if region else ''
    nestlib.pack = pack
    P0, C0, S0 = load_raw(region)
    space = candidate_space(C0, free)
    start = {r: P0['materialvalg'][r] for r in space if r != 'kolonner'}
    start['kolonner'] = P0['kolonner']
    base = evaluate(start, P0, C0, S0, False)
    nestlib.pack = _orig_pack
    base_greedy = evaluate(dict(start), P0, C0, S0, None)   # today's generator nesting, for reference
    nestlib.pack = pack
    print(('today: %s (greedy nesting %s) '+CURRENCY+', ok=%s') % (base['cost'], base_greedy['cost'], base['ok']))
    out = dict(today=base_greedy, t=time.strftime('%Y-%m-%dT%H:%M:%S'), free_look=free, region=region or 'oslo',
               currency=CURRENCY, sales_tax=TAX, machine_per_h=KR_PER_H, hw_per_drawer=HW_PER_DRAWER)
    with open(os.path.join(HERE, 'optimize_history%s.jsonl' % suf), 'w') as log:
        for strict in (False, True):
            best, n = climb(P0, C0, S0, space, start, strict, log)
            out['strict' if strict else 'loose'] = dict(best=best, evaluations=n)
            print(('%s: best %s '+CURRENCY+' after %d evaluations') % ('within Hettich width' if strict else 'any width', best and best['cost'], n))
    json.dump(out, open(os.path.join(HERE, 'optimize_result%s.json' % suf), 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
