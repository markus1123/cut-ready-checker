from fc.core import Finding
from fc.gx.core import gx_rule
from shapely.ops import unary_union

MIN_NECK = 8.0      # mm: narrower than this a strip across a part has a fraction of the part's strength
MIN_PIECE = 0.03    # each side of the neck holds >= 3 % of the part ...
MIN_PIECE_MM2 = 3000.0  # ... and >= ~55 x 55 mm: a real lobe of the part, not a tab, finger or decoration
MIN_PART = 20000.0  # mm2: furniture panels; small parts are trim / decoration
TOUCH = 0.5         # mm: a neck zone this close to a boundary is bounded by it
PATTERN = 3         # a thin zone running past this many openings is the web of a pattern of cut-outs


def neck(p):
    """-> (piece areas) if eroding the part by MIN_NECK/2 splits it into >= 2 big pieces, else None."""
    poly = p.poly
    if poly.is_empty or not poly.is_valid or poly.geom_type != 'Polygon':
        return None
    er = poly.buffer(-MIN_NECK / 2, join_style=2)
    if er.is_empty or er.geom_type != 'MultiPolygon':
        return None
    big = [x.area for x in er.geoms if x.area >= max(MIN_PIECE * poly.area, MIN_PIECE_MM2)]
    return big if len(big) >= 2 else None


def between_openings(p):
    """True if every thin zone of the part lies between its openings (does not reach the outline), or one thin zone
    runs past >= PATTERN openings: the thin material is the web of a pattern of cut-outs, not a notched panel."""
    poly = p.poly
    er = poly.buffer(-MIN_NECK / 2, join_style=2)
    back = unary_union([x.buffer(MIN_NECK / 2 + 0.3, join_style=2) for x in getattr(er, 'geoms', [er])])
    zs = [z for z in getattr(poly.difference(back), 'geoms', [poly.difference(back)]) if not z.is_empty and z.area >= 0.5]
    if not zs or not p.inner:
        return False
    ext = p.outer.exterior
    if not any(ext.distance(z) < TOUCH for z in zs):
        return True
    return any(sum(1 for i in p.inner if i.exterior.distance(z) < TOUCH) >= PATTERN for z in zs)


@gx_rule('GB04', 'Part held together by a neck narrower than 8 mm')
def check(g):
    """A part is only as strong as its narrowest cross-section. Where a notch, cut-out or concave outline leaves a
    neck under 8 mm wide between two substantial pieces of a panel, 12-25 mm plywood/MDF there is a matchstick:
    it breaks while the part is being cut (once the profile is nearly done the whole part hangs on that neck and
    the cutter pushes it), when the part is lifted off the bed, or at the first load in use - and in plywood half
    its fibres may be short grain. Opendesk and WikiHouse design guides ask for features no narrower than about
    the sheet thickness / bit diameter; 8 mm is well below that for any furniture sheet. Found by eroding the
    part (with its openings) by 4 mm: if it falls into two or more pieces that each hold >= 3 % of the part and
    >= 3000 mm2, those pieces are joined only by sub-8 mm material. Tabs, fingers and decoration are smaller
    than that and are left alone; parts under 20000 mm2 are trim, not panels.
    Narrowed after reading real files from other designers:
      * thin material that lies only BETWEEN openings (never reaching the outline), or that runs past 3+ openings, is
        the web of a designed pattern of cut-outs - kerf-bend / living-hinge slots, lattice and grille panels,
        slatted fronts - not a notch cutting a panel nearly in two; how close neighbouring openings may sit is
        judged by the opening-spacing rules (GC08), and the pattern bends or carries load as designed.
        Necks that reach the part outline (a notch, a concave pinch) are still flagged."""
    for p in g.parts:
        if p.outer.area < MIN_PART or not p.outer.is_valid:
            continue
        b = neck(p)
        if b and not between_openings(p):
            yield Finding('GB04', 'error', '%d big pieces of the part (%s mm2) are joined only by material narrower than %.0f mm: the part breaks at that neck while cut or in use' % (len(b), '/'.join('%.0f' % a for a in sorted(b, reverse=True)[:3]), MIN_NECK), p.key)
