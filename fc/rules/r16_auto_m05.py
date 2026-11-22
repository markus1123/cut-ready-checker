"""Cabinet member and drawer member of every slide must share one front reference when the drawer is closed."""
from fc.core import rule, Finding
from fc.world import frames, holes

MAX_OFFSET = 8.0   # mm: frontmost cabinet-member hole vs frontmost drawer-member hole, world depth, drawer closed


@rule('R16', 'Slide cabinet-member and drawer-member holes line up front-to-front (closed drawer), <= 8 mm apart')
def check(d):
    """Workshop reason: a side-mount slide's two members are positioned against each other at the front when closed
    (that is where the stop and the self/soft-close catch sit). The hole pattern of each member is measured from the
    slide's front end, and both members have their first screw hole about the same distance (~35-37 mm, 32-system)
    behind it. So, with the drawer in its closed position, the frontmost slide hole in the carcass wall and the
    frontmost slide hole in the drawer side must lie at (almost) the same depth. If they differ by roughly a front
    thickness, the pattern was taken from the wrong mounting drawing (inset vs overlay setback, +/- front
    thickness) or the box is drilled from the wrong reference: the front then hits the carcass before the slide
    reaches its stop (close never engages, drawer springs open) or the slide bottoms out with the front standing
    proud. Real slides differ by a few mm between members; MAX_OFFSET = 8 mm is under half an 18-19 mm front, so an
    inset/overlay mix-up is always caught. Checked in 3D per opening (all walls x rows), drawer at its assembled
    (closed) position, so a shifted carcass pattern, shifted drawer pattern or a shifted box are all caught."""
    S, info = d.S, d.info
    rows_z, half = info['slide_zc'], S['hoyde'] / 2
    T, Wo, cols = info['T'], info['Wo'], d.P['kolonner']
    cab, box = [], []           # (X, Y, Z) of slide holes / marks
    for f in frames(d):
        if f['code'] not in ('C', 'CH', 'D', 'S', 'SH'):
            continue
        tgt = box if f['code'] in ('S', 'SH') else cab
        for h in holes(f):
            if 'kinne' in h['op']['note']:
                tgt.append(h['entry'])
    out = []
    for c in range(cols):
        xl = T + c * (Wo + T); xr = xl + Wo
        for r, z in enumerate(rows_z):
            ys_c = [p[1] for p in cab if abs(p[2] - z) <= half and min(abs(p[0] - xl), abs(p[0] - xr)) < 0.5]
            ys_b = [p[1] for p in box if abs(p[2] - z) <= half + 2 and xl - 0.5 < p[0] < xr + 0.5]
            if not ys_c or not ys_b:
                continue
            off = min(ys_c) - min(ys_b)
            if abs(off) > MAX_OFFSET:
                out.append(Finding('R16', 'error',
                                   'Column %d, row %d: frontmost slide hole in the carcass at %.1f mm depth, in the '
                                   'closed drawer side at %.1f mm (%+.1f mm, max %g). The cabinet and drawer members '
                                   'do not meet front-to-front: inset/overlay setback mixed up (front is %.1f mm) - '
                                   'the drawer will not reach its stop/soft-close.'
                                   % (c + 1, r + 1, min(ys_c), min(ys_b), off, MAX_OFFSET, info['tf'])))
    return out[:8]
