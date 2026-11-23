"""R43 layer-name machining codes: every number the operator reads from a layer name is well-formed and equals the
geometry drawn on that layer.

Shared cause: the cutting file says the same thing twice - once as geometry and once as a code in the layer name
(D = tool/hole diameter, B = slot/groove width, Z = depth; 'P' is the decimal point, '6P4' = 6.4). In the workshop
(VCarve/Aspire on the ShopBot, and most layer-driven CAM: Fusion 'layer to operation', Alphacam, EnRoute) toolpaths
are assigned per layer and the operator sets the tool, pocket width and depth from the layer name. The geometry is
not re-measured. So when the code and the geometry disagree, the code wins and the cut is wrong. This happens when
a decimal marker is lost or doubled ('6P4' -> '64'), a field is truncated or mistyped, or the name is rebuilt by an
export or rename script that does not use the same number as the geometry.

Checks, on every sheet file including the test-cut kit:
(a) Grammar. Every layer that machines (prefix 01_ drill, 02_ through-hole, 03_ pocket, 04_ groove, 10_ contour)
    carries the fields its operation needs: 01/03 D and Z, 02 D, 04 B and Z, 10 Z. Each field is a number with at
    most one decimal marker 'P' followed by 1-2 digits (the generator rounds to 0.01 mm). Anything else ('6P4P',
    '6.4', 'B', 'D5,5') cannot be read reliably by the operator and is an error, not a guess.
(b) Width code = drawn width. Each closed polyline on a layer with a B code is a slot/groove/pocket rectangle. Its
    width (short side, measured rotation-free from area and perimeter) must equal B within 0.2 mm. Why 0.2 mm: the
    groove for a 5.9 mm hardboard drawer bottom is drawn 6.4 mm, so the fit clearance is only 0.3-0.5 mm (Blum/Hettich
    drawer bottom and common workshop practice: groove = panel + 0.5 mm). An error larger than 0.2 mm eats that
    clearance: the panel no longer slides in, or rattles. Larger errors (a lost decimal: 64 instead of 6.4)
    clear a pocket ten times too wide, through the confirmat holes and half the part.
(c) Diameter code = drawn circle on the kit sheets too (R34 covers the main sheets; the test kit is cut first and
    the operator's tool choice there is copied to the real job). Same 0.2 mm tolerance as R34.
"""
import math, re
from fc.core import rule, Finding

TOL = 0.2                                     # mm, see (b)
NUM = re.compile(r'^\d+(P\d{1,2})?$')
NEEDS = {'01': 'DZ', '02': 'D', '03': 'DZ', '04': 'BZ', '10': 'Z'}


def _fields(layer):
    """{'D': '5', 'Z': '11'} from '01_BOR_D5_Z11'. Only short tokens of a code letter followed by a digit or 'P'."""
    out = {}
    for tok in layer.split('_')[1:]:
        if len(tok) >= 2 and tok[0] in 'BDZ' and (tok[1].isdigit() or tok[1] in 'P.,'):
            out[tok[0]] = tok[1:]
        elif tok in ('B', 'D', 'Z'):
            out[tok] = ''
    return out


def _val(s):
    return float(s.replace('P', '.')) if NUM.match(s) else None


def _rect_width(pts):
    """Short side of a (possibly rotated) rectangle from its area and perimeter; exact for rectangles."""
    P = [p for p in pts if p[0] is not None]
    if len(P) > 1 and P[0] == P[-1]:
        P = P[:-1]
    if len(P) < 3:
        return None
    A = abs(sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))) / 2
    per = sum(math.hypot(P[(i + 1) % len(P)][0] - P[i][0], P[(i + 1) % len(P)][1] - P[i][1]) for i in range(len(P)))
    h = per / 2
    disc = h * h - 4 * A
    if disc < -1e-6:
        return None
    return (h - math.sqrt(max(disc, 0.0))) / 2


@rule('R43', 'Layer-name machining codes (D/B/Z) are well-formed and match the geometry drawn on the layer')
def layer_codes(d):
    out, seen = [], set()
    sheets = [(sh, False) for sh in d.sheets] + [(sh, True) for sh in getattr(d, 'kit_sheets', [])]
    for sh, kit in sheets:
        f = sh['file']
        for e in sh['ents']:
            L = e.get('layer', '')
            m = re.match(r'^(\d\d)_', L)
            if not m or m.group(1) not in NEEDS:
                continue
            F = _fields(L)
            key = (f, L)
            if key not in seen:
                bad = [k + F[k] for k in F if _val(F[k]) is None]
                miss = [k for k in NEEDS[m.group(1)] if k not in F]
                if m.group(1) == '02' and 'GJENNOM' in L:
                    miss = [k for k in miss if k != 'Z']
                if bad or miss:
                    seen.add(key)
                    out.append(Finding('R43', 'error', '%s: layer %s %s; the operator sets the tool from this name and '
                                       'cannot read it.' % (f, L, ', '.join(
                                           (['malformed code ' + ', '.join(bad)] if bad else []) +
                                           (['missing ' + '/'.join(miss) + ' code'] if miss else [])))))
                    continue
            if key in seen:
                continue
            if e['type'] == 'POLYLINE' and 'B' in F:
                B = _val(F['B'])
                w = _rect_width(e['pts'])
                if w is not None and abs(w - B) > TOL:
                    seen.add(key)
                    out.append(Finding('R43', 'error', '%s: layer %s says %g mm wide, but the slot drawn on it is %.2f mm; '
                                       'CAM will clear a %g mm pocket.' % (f, L, B, w, B)))
            elif e['type'] == 'CIRCLE' and kit and 'D' in F and 'r' in e:
                D = _val(F['D'])
                if abs(2 * e['r'] - D) > TOL:
                    seen.add(key)
                    out.append(Finding('R43', 'error', '%s: Ø%.2f circles on layer %s; the operator will drill them with '
                                       'a Ø%g bit.' % (f, 2 * e['r'], L, D)))
    return out
