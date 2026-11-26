from fc.core import Finding
from fc.gx.core import gx_rule
from shapely import affinity
from shapely.strtree import STRtree

MIN_OPEN = 100.0    # mm2: smaller openings are holes / marks, ignored for the pattern
MIN_PART = 20000.0  # mm2: a part with a real opening pattern (slots, cut-outs)
TOL = 0.02          # matched loops differ by < 2 % of their area (copies, CAD rounding)
MIN_N = 3           # openings in the pattern: a pair of loose loops can be a deliberate small part (built files have them)


@gx_rule('GG03', 'Part outline missing: only its openings are in the file, as loose loops')
def check(g):
    """A part's openings (slots, cut-outs) are cut first and its outline last; if the outline was on a hidden /
    frozen / non-cut layer when the DXF was exported, only the openings are left. The router then cuts them as loose
    slugs, throws them, and never cuts the part out: one part of the kit is missing (Vectric / Fusion DXF export:
    only visible layers are written; Opendesk making guide: check the file against the parts list). Evidence that
    this happened: a group of free-standing loops - not inside any part - that reproduces, loop for loop and in the
    same arrangement, the complete opening pattern (3+ openings) of another part in the same file (copies of a part
    are common in flat-pack kits), with free sheet all round them where that part's outline would be. Rotation and
    mirroring are allowed. (Loose keys / plugs drawn to fit a part's slots are nested elsewhere, among other parts.)"""
    parts = g.parts
    if len(parts) > 3000: return
    free = [p for p in parts if not p.inner and p.outer.is_valid and p.outer.area > MIN_OPEN * 0.5]
    if len(free) < 2: return
    fo = [p.outer for p in free]
    tree = STRtree(fo)
    done = set()
    for P in parts:
        if P.outer.area < MIN_PART: continue
        ops = [i for i in P.inner if i.area > MIN_OPEN and i.is_valid]
        if len(ops) < MIN_N or len(ops) > 60: continue
        ref = max(ops, key=lambda i: i.area)
        c0 = ref.centroid
        cands = [k for k, f in enumerate(fo) if abs(f.area - ref.area) < TOL * ref.area and k not in done]
        hit = None
        for k in cands:
            F = fo[k]; c1 = F.centroid
            for mir in (False, True):
                for ang in (0, 90, 180, 270):
                    def mv(x, mir=mir, ang=ang):
                        y = affinity.scale(x, -1, 1, origin=c0) if mir else x
                        y = affinity.rotate(y, ang, origin=c0)
                        return affinity.translate(y, c1.x - c0.x, c1.y - c0.y)
                    if mv(ref).symmetric_difference(F).area > TOL * ref.area: continue
                    got = []
                    for o in ops:
                        m = mv(o)
                        js = [int(j) for j in tree.query(m) if int(j) not in got and
                              abs(fo[int(j)].area - o.area) < TOL * o.area and
                              fo[int(j)].symmetric_difference(m).area < TOL * o.area]
                        if not js: break
                        got.append(js[0])
                    else:
                        # the lost outline's footprint must be free sheet: nothing else is nested where it would be
                        foot = mv(P.outer)
                        mine = {id(free[j]) for j in got}
                        if all(q.outer.intersection(foot).area < 0.01 * q.outer.area for q in parts
                               if id(q) not in mine and q.outer.is_valid and q.outer.intersects(foot)):
                            hit = got
                    if hit: break
                if hit: break
            if hit: break
        if hit:
            done.update(hit)
            f = free[hit[0]]
            yield Finding('GG03', 'error',
                          '%d loose loops here match, loop for loop, all the openings of another part in this file, but '
                          'no outline encloses them: this copy\'s outline is missing - the openings are cut as slugs and '
                          'the part is never cut out' % len(hit), f.key)
