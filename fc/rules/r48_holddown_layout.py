"""Hold-down at a workshop that screws the sheet down (Fellesverkstedet wiki, 'Preparing 2D files'): draw a circle
(Ø25 with a 6 mm bit, Ø28 with 8 mm) where each screw goes; the machine marks its centre. 25 mm between parts and
from the sheet edge leaves room for them; 3-4 screws close to each part. A circle that reaches into a part puts a
screw in the bit's path (FAQ: 'Check if you perhaps accidentally milled a screw' - a broken bit)."""
import math
from fc.core import rule, Finding
from fc import machine

TOL = 0.5


def _gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0.0); dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return math.hypot(dx, dy) if dx and dy else max(dx, dy)


@rule('R48', 'Sheets carry hold-down screw circles of the workshop size, clear of every part, near every part')
def check(d):
    V = d.P['verksted']
    if (V.get('holdning') or machine.HOLD['method']) != 'skruer':
        return []
    H, need = machine.HOLD, machine.circle_d(V['fres_stor_d'])
    out = []
    for sh in list(d.sheets) + list(getattr(d, 'kit_sheets', [])):
        f = sh['file']
        parts = [e['bbox'] for e in sh['ents'] if e['type'] == 'POLYLINE' and e.get('layer', '').startswith('10_KONTUR')]
        if not parts:
            continue
        circ = [e for e in sh['ents'] if e['type'] == 'CIRCLE' and 'HOLDDOWN' in e.get('layer', '').upper() and 'x' in e]
        if not circ:
            out.append(Finding('R48', 'error', '%s: no hold-down circles. The sheet is screwed down; screws placed by eye '
                               'end up in the toolpath.' % f))
            continue
        small = [c for c in circ if 2 * c['r'] < need - TOL]
        if small:
            out.append(Finding('R48', 'error', '%s: hold-down circles Ø%g, the workshop asks for Ø%g with a Ø%g bit.'
                               % (f, 2 * small[0]['r'], need, V['fres_stor_d'])))
        for c in circ:
            hit = [b for b in parts if _gap((c['x'], c['y'], c['x'], c['y']), b) < c['r'] - TOL]
            if hit:
                out.append(Finding('R48', 'error', '%s: hold-down circle at (%.0f, %.0f) reaches into a part: the screw sits '
                                   'in the bit\'s path.' % (f, c['x'], c['y'])))
                break
        reach = H['gap_min'] / 2 + need / 2 + 1
        lonely = sum(1 for b in parts
                     if sum(1 for c in circ if _gap((c['x'], c['y'], c['x'], c['y']), b) <= reach) < H['per_part_min'])
        if lonely:
            out.append(Finding('R48', 'warn', '%s: %d part(s) have fewer than %d hold-down screws next to them (wiki: 3-4 per part).'
                               % (f, lonely, H['per_part_min'])))
        tight = min((_gap(a, b) for i, a in enumerate(parts) for b in parts[i + 1:]), default=None)
        if tight is not None and tight < H['gap_min'] - TOL:
            out.append(Finding('R48', 'warn', '%s: parts only %.0f mm apart; the workshop asks for %g mm (room for a screw).'
                               % (f, tight, H['gap_min'])))
        if sh.get('W') and sh.get('H'):
            edge = min(min(b[0], b[1], sh['W'] - b[2], sh['H'] - b[3]) for b in parts)
            if edge < H['edge_min'] - TOL:
                out.append(Finding('R48', 'warn', '%s: a part is %.0f mm from the sheet edge; the workshop asks for %g mm.'
                                   % (f, edge, H['edge_min'])))
    return out
