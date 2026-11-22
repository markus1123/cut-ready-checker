"""Drawer box built from the ACTUAL parts (not the generator's intent): width vs opening, grooves aligned,
bottom fits the grooves, bottom does not sag, tolerance stack-up."""
import math, random
from fc.core import rule, Finding

E_MOD = {'huntonit': 2500.0, 'hdf': 3500.0, 'mdf': 3000.0}    # MPa, conservative
LOAD_KG = 12.0


def _p(d, code):
    return d.by.get(code)


@rule('R07', 'Drawer box from the real parts: fits the slides, grooves line up, bottom fits and does not sag')
def check(d):
    out = []
    S, P = d.S, d.P
    s, sh, e1, e2, sb, b, w = (_p(d, c) for c in ('S', 'SH', 'E1', 'E2', 'SB', 'B', 'D'))
    sh = sh or s
    cols = P['kolonner']
    opening = (b['L'] - (cols - 1) * (w['t'] if w else 0)) / cols
    bw = e1['L'] + s['t'] + sh['t']
    clr = (opening - bw) / 2
    need = S['sideklaring']
    if clr < need - 0.01:
        out.append(Finding('R07', 'error', 'Drawer box %.1f in opening %.1f: %.2f mm per side, slide needs %.1f. Drawer binds.' % (bw, opening, clr, need)))
    elif clr > need + 1.0:
        out.append(Finding('R07', 'error', 'Drawer box %.1f in opening %.1f: %.2f mm per side, slide max ~%.1f. Slide will not engage.' % (bw, opening, clr, need + 1.0)))
    if abs(e1['L'] - e2['L']) > 0.05:
        out.append(Finding('R07', 'error', 'Front end E1 (%g) and back end E2 (%g) differ - box is a trapezoid.' % (e1['L'], e2['L'])))
    if abs(s['L'] - sh['L']) > 0.05:
        out.append(Finding('R07', 'error', 'Left and right drawer sides differ in length (%g vs %g).' % (s['L'], sh['L'])))
    # grooves: same height on all four parts (y from the bottom edge on all of them)
    gs = {}
    for p in (s, sh, e1, e2):
        g = [o for o in p['ops'] if o['kind'] == 'groove']
        if len(g) != 1:
            out.append(Finding('R07', 'error', '%s has %d bottom grooves.' % (p['code'], len(g)), p['code'])); continue
        gs[p['code']] = g[0]
    if len(gs) == 4:
        y1s = [g['y1'] for g in gs.values()]; y2s = [g['y2'] for g in gs.values()]
        if max(y1s) - min(y1s) > 0.2 or max(y2s) - min(y2s) > 0.2:
            out.append(Finding('R07', 'error', 'Bottom grooves at different heights: %s. Bottom cannot enter all four.'
                               % ', '.join('%s %g-%g' % (k, g['y1'], g['y2']) for k, g in gs.items())))
        g = gs['S']; nd = g['z']; gw = g['y2'] - g['y1']
        if gw < sb['t'] + 0.2:
            out.append(Finding('R07', 'error', 'Groove %.2f mm for a %.2f mm bottom - too tight to slide in.' % (gw, sb['t'])))
        if gw > sb['t'] + 1.2:
            out.append(Finding('R07', 'error', 'Groove %.2f mm for a %.2f mm bottom - bottom rattles.' % (gw, sb['t'])))
        for span, have, name in ((e1['L'] + 2 * nd, sb['L'], 'width'), (s['L'] - s['t'] - sh['t'] + 2 * nd, sb['B'], 'depth')):
            if have > span - 0.6:
                out.append(Finding('R07', 'error', 'Bottom %s %.1f > groove-to-groove %.1f minus play - box cannot close.' % (name, have, span)))
            if have < span - 2 * nd + 2 * 0.6 * nd:
                out.append(Finding('R07', 'error', 'Bottom %s %.1f sits less than 60%% into the grooves (span %.1f).' % (name, have, span)))
    # sag: plate simply supported on 4 edges, uniform load (Timoshenko alpha table)
    a, bb = max(sb['L'], sb['B']), min(sb['L'], sb['B'])
    r = a / bb
    alpha = [(1.0, .00406), (1.2, .00564), (1.4, .00705), (1.6, .00830), (1.8, .00931), (2.0, .01013), (3.0, .01223), (99, .01302)]
    al = next(v for k, v in alpha if r <= k)
    mat = (P['_valg'].get('skuffebunn') or {}).get('navn', '').lower()
    E = next((v for k, v in E_MOD.items() if k in mat), 3000.0)
    t = sb['t']
    D = E * t ** 3 / (12 * (1 - 0.3 ** 2))
    q = LOAD_KG * 9.81 / (sb['L'] * sb['B'])
    wmax = al * q * bb ** 4 / D
    if wmax > 3.0:
        out.append(Finding('R07', 'error', 'Drawer bottom %.1f mm board, %gx%g: sags ~%.1f mm under %g kg (limit 3). Use thicker board or a centre support.'
                           % (t, sb['L'], sb['B'], wmax, LOAD_KG)))
    elif wmax > 2.0:
        out.append(Finding('R07', 'warn', 'Drawer bottom sags ~%.1f mm under %g kg.' % (wmax, LOAD_KG)))
    # tolerance stack-up (Monte Carlo): cut +-0.2 (sigma .1), board local thickness sigma .08, wall position sigma .15
    rnd = random.Random(1)
    n, bad = 4000, 0
    for _ in range(n):
        op = opening + rnd.gauss(0, .1) + rnd.gauss(0, .15)
        bx = e1['L'] + rnd.gauss(0, .1) + s['t'] + sh['t'] + rnd.gauss(0, .08) * 2
        if (op - bx) / 2 < need - 0.1:
            bad += 1
    pb = bad / n
    drawers = P['rader'] * cols
    pany = 1 - (1 - pb) ** drawers
    if pany > 0.25:
        out.append(Finding('R07', 'error', 'Tolerance stack-up: %.0f%% chance at least one of %d drawers binds (margin %.2f mm/side).' % (100 * pany, drawers, clr - need)))
    elif pany > 0.05:
        out.append(Finding('R07', 'warn', 'Tolerance stack-up: %.0f%% chance at least one of %d drawers is tight (margin %.2f mm/side).' % (100 * pany, drawers, clr - need)))
    return out
