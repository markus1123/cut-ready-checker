"""Cut size = finished size - band thickness on each banded edge (cabinet-software rule, Microvellum KB;
docs/rules-from-manuals.md §6). The generator lists cut size = finished size, which is only OK for thin
iron-on banding. Above 1 mm of growth per direction, parts no longer fit their opening."""
from fc.core import rule, Finding
from fc.rules.r06_bands import band_edges

MAX_GROWTH = 1.0


@rule('R23', 'Edge banding thickness is stated, and the growth it adds per direction is <= 1 mm (else cut sizes must deduct it)')
def check(d):
    F = d.P['front']
    b = F.get('kantlist_tykkelse')
    out = []
    if b is None:
        out.append(Finding('R23', 'warn', 'Edge band thickness not stated (front.kantlist_tykkelse); assuming 0.5 mm iron-on.'))
        b = 0.5
    if d.P.get('kantlist_trekkes_fra'):
        return out
    for p in d.parts:
        e = band_edges(p)
        gx = b * len(e & {'x0', 'xL'})
        gy = b * len(e & {'y0', 'yB'})
        if max(gx, gy) > MAX_GROWTH:
            out.append(Finding('R23', 'error', '%s grows %.1f mm with %.1f mm banding but is cut at finished size; reduce the cut size.'
                               % (p['code'], max(gx, gy), b), p['code']))
    return out
