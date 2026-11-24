"""R46 bridge to the geometry-only rule set (fc/gx, G01..): those rules read any designer's DXF with no 3D model.
They are learned by a separate loop over a corpus of real open designs (Opendesk, AtFAB, Fellesverkstedet).
Running them here on the kommode's sheet files adds their checks (hole too close to the edge, round cut-out below
the smallest bit, hole exported as a coarse polygon, one hole off its row, ...) and picks up every new G rule that
loop accepts, with no copying.  Only the sheet files that are cut are checked (not the all-parts overview).
"""
import glob
import hashlib
import os
from fc.core import rule, Finding

SKIP = ('00_',)   # overview drawing: every part side by side, not a cutting file
_CACHE = {}       # file content hash -> findings (most faults leave the sheet files unchanged)


@rule('R46', 'Every sheet file passes the corpus-trained geometry rules (G01..), which work on any designer\'s DXF')
def gx_bridge(d):
    from fc.gx import model, core
    out = []
    for fn in sorted(glob.glob(os.path.join(d.out, '*.dxf'))):
        name = os.path.basename(fn)
        if name.startswith(SKIP):
            continue
        key = hashlib.md5(open(fn, 'rb').read()).hexdigest()
        if key not in _CACHE:
            try:
                _CACHE[key] = core.run(model.parse(fn))[0]
            except Exception:
                _CACHE[key] = []
        found = _CACHE[key]
        seen = set()
        for f in found:
            if f.severity != 'error' or f.rule in seen:
                continue
            seen.add(f.rule)
            out.append(Finding('R46', 'error', '%s: %s %s' % (name, f.rule, f.msg), f.part))
    return out
