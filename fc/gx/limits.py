"""Tool and machine limits for the generic (any designer) rules.

Default: world-generic limits, because a file from anywhere may be cut on any router:
  BIT_MIN 3.175  smallest router bit that still cuts through furniture sheet (1/8", Amana 46180, 20.6 mm flute)
  FINEST  1.6    finest end mill made for routing sheet at all (1/16")
  CONTOUR_R 3.0  radius of the usual contour bit (6 mm / 1/4"): what an inside corner is left with
  SHEETS         largest common furniture sheet formats; Z_MAX None (not checked)

Opt-in workshop mode, FC_SHOP=<profile> (fc/machines/<profile>.json, e.g. fellesverkstedet): the same rules judge
the file against THAT workshop's real bits and bed - is this file cut-ready *there*?
"""
import os

BIT_MIN, FINEST, CONTOUR_R = 3.175, 1.6, 3.0
SHEETS = [(2500, 1250), (3050, 1525)]
Z_MAX = None
SHOP = os.environ.get('FC_SHOP') or None

if SHOP:
    os.environ['FC_MACHINE'] = SHOP
    from fc import machine as _m
    _mills = sorted(_m.endmills(), key=lambda b: b['d'])
    FINEST = _mills[0]['d']                                             # the shop's smallest end mill
    # through-cuts: bits under 3 mm have ~6-9 mm flutes and do not reach through furniture sheet; the shop's database
    # stores no flute lengths, so take its smallest bit of >= 3 mm (a known flute >= 12 mm would also qualify)
    BIT_MIN = min(b['d'] for b in _mills if b['d'] >= 3.0 or (b['flute_len'] or 0) >= 12)
    _contour = [b for b in _mills if (b['flute_len'] or b['flute_len_min'] or 0) >= 12] or _mills[-1:]
    CONTOUR_R = _contour[0]['d'] / 2                                    # smallest bit known to reach through a sheet
    SHEETS = [tuple(_m.BED)]
    Z_MAX = _m.Z_MAX
