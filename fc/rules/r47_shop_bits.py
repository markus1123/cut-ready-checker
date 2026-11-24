"""The bits the design plans with must be bits the workshop actually has. Toolpaths and tool compensation are made
for one diameter; cutting with another leaves every slot, hole and outline off by the difference (Fellesverkstedet
FAQ: 'Check if the milling bit you put in the machine corresponds to the diameter you used for creating the
tool-paths'). Source of the bit list: the workshop's VCarve tool database (fc/machines/, fc/machine.py)."""
from fc.core import rule, Finding
from fc import machine


@rule('R47', 'Planned bit diameters exist in the workshop; melamine gets a compression or downcut bit')
def check(d):
    V = d.P['verksted']
    have = sorted({b['d'] for b in machine.endmills()})
    out = []
    for dk in ('fres_liten_d', 'fres_stor_d'):
        dia = V[dk]
        if machine.bit(dia) is None:
            near = min(have, key=lambda k: abs(k - dia))
            out.append(Finding('R47', 'error', 'Toolpaths planned for a Ø%g bit (%s), but %s has end mills of %s mm. '
                               'With the nearest (Ø%g) every hole, slot and outline is %.2f mm off.'
                               % (dia, dk, machine.M['name'], '/'.join('%g' % k for k in have), near, abs(near - dia))))
    big = V['fres_stor_d']
    if 'melamin' in str(d.P.get('_valg', '')).lower():
        clean = [b for b in machine.endmills() if (b['compression'] or b['downcut']) and abs(b['d'] - big) <= 0.05]
        if not clean:
            out.append(Finding('R47', 'warn', 'Melamine boards, but the workshop has no Ø%g compression or downcut bit '
                               '(an upcut chips the top face). Buy one or ask what they have in stock.' % big))
    return out
