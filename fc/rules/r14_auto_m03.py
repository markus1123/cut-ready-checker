"""Parts cut from a board with grain (wood decor, veneer, plywood) must keep the grain direction on the sheet."""
from fc.core import rule, Finding

# Words in a catalogue name/id that mean the face has a directional grain pattern (printed decor or real wood).
GRAIN_WORDS = ('eik', 'oak', 'ask', 'ash', 'valnøtt', 'valnott', 'walnut', 'bjørk', 'bjork', 'birch', 'furu', 'pine',
               'teak', 'kirsebær', 'cherry', 'lønn', 'maple', 'alm', 'elm', 'finer', 'veneer', 'kryssfiner', 'plywood')
SQUARE_TOL = 1.0   # mm: a part this close to square has no defined grain direction in the nest
TOL = 0.6          # mm: placed contour vs cut-list size


def has_grain(m):
    """A board has grain if the catalogue renders it as wood or its name/id names a wood species or veneer."""
    if isinstance(m.get('dekor'), dict) and 'wood' in m['dekor']:
        return True
    s = ('%s %s' % (m.get('id', ''), m.get('navn', ''))).lower()
    return any(w in s for w in GRAIN_WORDS)


def _placed(sheets, mid):
    """{code: [(w, h, sheet file, label)]} for every part outline on the sheets of material id `mid`."""
    out = {}
    for sh in sheets:
        if mid not in sh['file']:
            continue
        rects = [e['bbox'] for e in sh['ents'] if e['type'] == 'POLYLINE' and e.get('layer', '').startswith('10_KONTUR')]
        for t in (e for e in sh['ents'] if e['type'] == 'TEXT' and e.get('text')):
            hit = [r for r in rects if r[0] < t['x'] < r[2] and r[1] < t['y'] < r[3]]
            if not hit:
                continue
            r = min(hit, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
            out.setdefault(t['text'].split()[0], []).append((r[2] - r[0], r[3] - r[1], sh['file'], t['text']))
    return out


@rule('R14', 'Boards with grain (wood decor/veneer) are nested with rotation locked: every part keeps its grain direction')
def check(d):
    """Workshop reason: oak/walnut decor melamine, veneer and plywood have a grain that runs along the sheet length.
    The generator's convention is that a part's x (L) runs along the sheet's grain. If the material is not marked
    'retning' (grain lock), the nester is free to turn parts 90° to fill the sheet. Turned parts come out with the
    grain running the other way: the two visible sides, or a row of drawer fronts, no longer match, and the odd part
    has to be re-cut from a new (expensive) decor sheet. This cannot be fixed after cutting, so it stops the job.
    Checked twice: (1) the catalogue entry of any grained board used must have retning=true, and (2) on the DXFs the
    operator imports, every non-square part on a grained board must be placed L along X, B along Y (not rotated)."""
    out, seen = [], set()
    for role, m in sorted(d.P.get('_valg', {}).items()):
        if not m or not has_grain(m) or not any(p['mat'] == role for p in d.parts):
            continue
        mid = m['id']
        if not m.get('retning') and mid not in seen:
            seen.add(mid)
            out.append(Finding('R14', 'error', '%s (%s) has a wood grain but is marked retning=false: the nester may '
                               'rotate parts 90° and the grain will not match between parts.' % (m['navn'], mid)))
        placed = _placed(d.sheets, mid)
        for p in d.parts:
            if p['mat'] != role or abs(p['L'] - p['B']) <= SQUARE_TOL:
                continue
            for w, h, fn, lbl in placed.get(p['code'], []):
                if abs(w - p['B']) <= TOL and abs(h - p['L']) <= TOL:
                    key = (fn, lbl)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(Finding('R14', 'error', '%s: "%s" is placed rotated 90° (%gx%g on the sheet, cut list '
                                       '%gx%g): its grain runs across the grain of the other %s parts.'
                                       % (fn, lbl, w, h, p['L'], p['B'], mid), p['code']))
    return out
