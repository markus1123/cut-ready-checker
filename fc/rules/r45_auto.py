"""R45 board per function: every part is cut from the sheet product chosen for what that part DOES in the chest.

Class of mistake: a part ends up on the wrong board (a generator bug in the part -> material map, a nesting/export
bug that puts labels on another board's sheet, or a cut list naming another product). Melamine decors cannot be
changed after cutting: an oak front cut from white carcass board, or a carcass bottom cut from 3 mm hardboard,
is scrap plus a wasted sheet, and the sheet meant for it comes back half empty.

The checker states the function of each part code itself (independent of the generator's `mat` field):
    K fronts                         -> 'front'      (visible decor face)
    A top, C/CH sides                -> 'ytre'       (visible outer carcass)
    B bottom, D middle wall, H plinth-> 'korpus'
    S/SH drawer sides, E1/E2 ends    -> 'skuff'
    SB drawer bottoms                -> 'skuffebunn' (sits in a groove; thickness must suit it)
    G back panel                     -> 'bakplate'
Unknown codes fall back to keywords in the part name.

Checks (all errors; tolerance 0 for board identity because it is a yes/no fact):
 1. model: the board the part is assigned to is the board chosen for its function (same catalogue id; if two
    functions share one product it does not matter which role name is used).
 2. files: the sheet DXF that carries a part's label is named after that board (the operator loads the sheet
    named on the file).
 3. cut list: the 'Materiale' column of kappliste.csv names that board's product.
 4. thickness: the part's thickness equals the measured thickness for its function within 0.3 mm
    (chipboard tolerance per EN 312 is +-0.3 mm; a larger difference means a different product).
 5. the chosen product is listed in the catalogue as suitable ('roller') for that function, e.g. a 3 mm
    hardboard is not a drawer box side (workshop practice; the generator only warns about this).
"""
import csv, io, re
from fc.core import rule, Finding

ROLE_OF = {'K': 'front', 'A': 'ytre', 'C': 'ytre', 'CH': 'ytre', 'B': 'korpus', 'D': 'korpus', 'H': 'korpus',
           'S': 'skuff', 'SH': 'skuff', 'E1': 'skuff', 'E2': 'skuff', 'SB': 'skuffebunn', 'G': 'bakplate'}
NAME_KEYS = [('front', 'front'), ('skuffebunn', 'skuffebunn'), ('skuff', 'skuff'), ('bakplate', 'bakplate'),
             ('topp', 'ytre'), ('side', 'ytre'), ('bunn', 'korpus'), ('vegg', 'korpus'), ('list', 'korpus')]
THK_KEY = {'front': 'front', 'ytre': 'korpus', 'korpus': 'korpus', 'skuff': 'skuff', 'skuffebunn': 'skuffebunn',
           'bakplate': 'bakplate'}
THK_TOL = 0.3


def role_of(p):
    if p['code'] in ROLE_OF:
        return ROLE_OF[p['code']]
    n = p.get('name', '').lower()
    return next((r for k, r in NAME_KEYS if k in n), None)


def _label(m):
    return '%s (%s %s)' % (m['navn'], m['leverandor'], m['artnr'])


@rule('R45', 'Every part is cut from the board chosen for its function (model, sheet files, cut list, thickness)')
def check(d):
    V = d.P.get('_valg', {})
    out = []
    want = {}
    for p in d.parts:
        r = role_of(p)
        if r is None or r not in V:
            continue
        m = V[r]
        want[p['code']] = m
        got = V.get(p.get('mat'))
        if got is None or got['id'] != m['id']:
            out.append(Finding('R45', 'error', '%s (%s) is a %s part but is assigned to %s; chosen board is %s.'
                               % (p['code'], p['name'], r, got['navn'] if got else p.get('mat'), m['navn']), p['code']))
        tk = d.P.get('tykkelse_malt', {}).get(THK_KEY[r])
        if tk is not None and abs(float(p['t']) - float(tk)) > THK_TOL:
            out.append(Finding('R45', 'error', '%s is %.1f mm thick; the %s board is measured %.1f mm (tol %.1f).'
                               % (p['code'], p['t'], r, tk, THK_TOL), p['code']))
        if r not in m.get('roller', [r]):
            out.append(Finding('R45', 'error', '%s chosen for %s (%s) is not listed as suitable for that use.'
                               % (m['navn'], r, p['code']), p['code']))
    # 2. sheet files
    for sh in d.sheets:
        mm = re.match(r'^[a-z]+\d+_(.+)_\d+x\d+\.dxf$', sh['file'])
        if not mm:
            continue
        bad = sorted({t['text'].split(' ')[0] for t in sh['ents'] if t['type'] == 'TEXT' and t.get('text')
                      and t['text'].split(' ')[0] in want and want[t['text'].split(' ')[0]]['id'] != mm.group(1)})
        if bad:
            out.append(Finding('R45', 'error', '%s carries %s, which must be cut from %s.'
                               % (sh['file'], ', '.join(bad), ', '.join(sorted({want[c]['id'] for c in bad})))))
    # 3. cut list
    txt = d.files.get('kappliste.csv')
    if txt:
        rows = list(csv.reader(io.StringIO(txt), delimiter=';'))
        if rows and 'Materiale' in rows[0] and 'Del' in rows[0]:
            ci, mi = rows[0].index('Del'), rows[0].index('Materiale')
            for row in rows[1:]:
                if len(row) > max(ci, mi) and row[ci] in want and row[mi] != _label(want[row[ci]]):
                    out.append(Finding('R45', 'error', 'kappliste.csv: %s listed as "%s", must be %s.'
                                       % (row[ci], row[mi][:50], want[row[ci]]['navn']), row[ci]))
    return out
