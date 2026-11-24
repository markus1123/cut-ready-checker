"""Every hole fits the hardware that goes in it. A screw or bolt that passes through a part needs clearance (>= its
diameter + 0.5 mm); a screw that bites needs a pilot of about 60-80 % of its diameter in chipboard; fittings with a
fixed drilling (Minifix, dowels, confirmat pilots) need exactly that drill.
Sources: Häfele Minifix 15 (face bolt Ø5, edge bolt Ø8), Hettich/Häfele confirmat 7x50 (Ø7 passage, Ø5 pilot),
Spax/Würth chipboard screws (pilot 60-80 % of d), ISO 273 clearance for M4 (4.5 medium)."""
import re
from fc.core import rule, Finding

PILOT = (0.6, 0.8)


def _need(kind, d_screw_note, note):
    """-> (lo, hi, what) for this hole, or None if the note names no hardware we know."""
    n = note.lower()
    if 'minifix-bolt' in n:
        return (7.7, 8.3, 'Minifix edge bolt (Ø8 drill)') if kind == 'edge' else (4.7, 5.3, 'Minifix screw-in bolt (Ø5 drill)')
    if 'minifix-hus' in n:
        return (14.7, 15.3, 'Minifix 15 housing')
    if n.startswith('plugg'):
        return (7.8, 8.2, 'Ø8 dowel')
    if 'konfirmat' in n:
        return (4.7, 5.3, 'confirmat pilot (Ø5)') if (kind == 'edge' or 'forbor' in n) else (6.8, 10.5, 'confirmat 7 mm shank')
    if 'håndtak' in n or 'handtak' in n:
        return (4.5, 10.5, 'M4 handle bolt clearance')
    m = re.search(r'(\d+(?:[.,]\d)?)x\d+', n)
    sd = float(m.group(1).replace(',', '.')) if m else d_screw_note
    if 'forbor' in n or 'pilot' in n:
        if sd:
            return (PILOT[0] * sd, PILOT[1] * sd + 0.05, 'pilot for a Ø%g screw' % sd)
        return None
    if kind == 'through' and sd and 'skrue' in n:
        return (sd + 0.5, sd + 4.5, 'clearance for a Ø%g screw' % sd)
    return None


@rule('R49', 'Hole diameters fit the hardware named for them (clearance, pilot or fixed fitting drill)')
def check(d):
    slide_screw = (d.S or {}).get('skrue_d', 4.0)
    out, seen = [], set()
    for p in d.parts:
        for o in p['ops']:
            if o['kind'] in ('groove', 'mark') or not o.get('d'):
                continue
            note = o.get('note') or ''
            need = _need(o['kind'], slide_screw if 'skinne' in note.lower() else None, note)
            if not need:
                continue
            lo, hi, what = need
            if not (lo - 1e-6 <= o['d'] <= hi + 1e-6):
                key = (p['code'], note, o['d'])
                if key in seen:
                    continue
                seen.add(key)
                out.append(Finding('R49', 'error', '%s: "%s" is Ø%g; a %s needs Ø%.1f-%.1f.' % (p['code'], note, o['d'], what, lo, hi), p['code']))
    return out
