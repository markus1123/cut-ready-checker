"""A router bit can only cut as deep as its flute. Small holes through a 19 mm board need a long 1/8\" bit."""
from fc.core import rule, Finding
import nestlib


@rule('R11', 'Every CNC hole/pocket/groove depth fits the flute length of the bit that must cut it')
def check(d):
    V = d.P['verksted']
    small, big = V['fres_liten_d'], V['fres_stor_d']
    fl_s, fl_b = V.get('fres_liten_skjaerlengde'), V.get('fres_stor_skjaerlengde')
    if fl_s is None or fl_b is None:
        return [Finding('R11', 'error', 'Flute (cutting) length of the bits is unknown - ask the workshop (verksted.fres_*_skjaerlengde).')]
    out, seen = [], set()
    for p in d.parts:
        for o in nestlib.classify(p, []):
            if o[0] == 'GROOVE':
                dia, depth, note = o[2] - o[1], o[3], o[4]
            else:
                _, x, y, dia, depth, note = o
                if o[0] == 'THRU':
                    depth = p['t'] + 0.3
            bit, fl = (big, fl_b) if dia >= big - 0.01 else (small, fl_s)
            if depth > fl:
                key = (p['code'], note, dia)
                if key in seen:
                    continue
                seen.add(key)
                out.append(Finding('R11', 'error', '%s: %s Ø%g needs %.1f mm depth with the Ø%g bit (flute %.1f). Spot it on the CNC and drill through by hand, or get a longer bit.'
                                   % (p['code'], note, dia, depth, bit, fl), p['code']))
    return out
