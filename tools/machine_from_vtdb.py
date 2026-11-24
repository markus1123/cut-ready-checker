#!/usr/bin/env python3
"""Build fc/machines/fellesverkstedet.json: the workshop's real machine + tools, for the checker's rules.

    python3 -I tools/machine_from_vtdb.py "<path to 201027 Fellesverkstedet Vcarve tool Database.vtdb>"

Tools come from the workshop's own VCarve tool database (SQLite, read-only). Machine and hold-down values come from
their wiki (fellesverkstedet.notion.site -> CNC), read 2026-11-24; they are typed in below with the page they come from.
Feeds in a .vtdb with rate_units 0 are mm/s (ShopBot speeds are per second): stored here as mm/min.
"""
import json, os, sqlite3, sys

WIKI = 'https://fellesverkstedet.notion.site/CNC-c8a862efdc5a490c9c88aebecad0ac88'
PREP = 'https://fellesverkstedet.notion.site/Preparing-2D-files-3f126a378fc5433dad4fc41ef8a5f689'
FAQ = 'https://fellesverkstedet.notion.site/FAQ-6fe046146ef6439c89a2779ed4d5ace9'
CAM = 'https://fellesverkstedet.notion.site/CAM-Creating-toolpaths-for-running-the-machine-f4293cdb74b04c0695f6fb8df9ee634c'
TYPES = {0: 'ballnose', 1: 'endmill', 3: 'vbit'}


def main(path):
    c = sqlite3.connect('file:%s?immutable=1' % path, uri=True)
    grp = {i: n for i, n in c.execute('select id, name from tool_tree_entry where tool_geometry_id is null')}
    cut = {}
    for gid, feed, plunge, rpm, step, ru in c.execute(
            'select t.tool_geometry_id, d.feed_rate, d.plunge_rate, d.spindle_speed, d.stepdown, d.rate_units '
            'from tool_entity t join tool_cutting_data d on d.id = t.tool_cutting_data_id'):
        cut.setdefault(gid, (feed, plunge, rpm, step, ru))
    bits = []
    for name, pg, tt, units, dia, nfl, fl, gid in c.execute(
            'select g.name_format, e.parent_group_id, g.tool_type, g.units, g.diameter, g.num_flutes, g.flute_length, g.id '
            'from tool_tree_entry e join tool_geometry g on g.id = e.tool_geometry_id'):
        group = grp.get(pg, '')
        mat = next((m for m in ('wood', 'plastic', 'metal', 'foam') if m in group.lower()), 'other')
        feed, plunge, rpm, step, ru = cut.get(gid, (None,) * 5)
        k = 60.0 if ru == 0 else 1.0
        bits.append(dict(
            d=round(dia, 3), type=TYPES.get(tt, str(tt)), flutes=nfl, material=mat,
            downcut='downcut' in (name or '').lower(), compression='compression' in (name or '').lower(),
            feed_mm_min=round(feed * k) if feed else None, plunge_mm_min=round(plunge * k) if plunge else None,
            rpm=rpm, stepdown=step,
            flute_len=fl,                       # not filled in their database
            flute_len_min=step if tt == 1 else None,   # a pass can't be deeper than the flute: lower bound
            name=(name or '').replace('{Diameter|F}{Units Short}', '%gmm' % dia)))
    bits.sort(key=lambda b: (b['material'], b['type'], b['d']))
    prof = dict(
        name='Fellesverkstedet, Oslo: 2x ShopBot PRS Alpha',
        sources=dict(tools='201027 Fellesverkstedet Vcarve tool Database.vtdb (from the wiki, ' + CAM + ')',
                     machine=WIKI, file_prep=PREP, faq=FAQ, read='2026-11-24'),
        units='mm', cam='VCarve 12.13 (Windows)',
        bed=[2440.0, 1220.0], z_max=60.0, precision=0.05, rpm_max=18000,
        holddown=dict(method='skruer',
                      note='Sheet is screwed to the sacrificial layer; the machine drills the centre of each hold-down '
                           'circle as a screw mark. 3-4 screws close to each part.',
                      circle_d={'6': 25.0, '8': 28.0}, gap_min=25.0, edge_min=25.0, per_part_min=2,
                      source=PREP),
        thickness_note='Never trust nominal sheet thickness: 18 mm sheets measured 17.5-18.5 (FAQ/wiki).',
        bits=bits)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fc', 'machines', 'fellesverkstedet.json')
    json.dump(prof, open(out, 'w'), indent=1, ensure_ascii=False)
    print('wrote', os.path.normpath(out), len(bits), 'bits')


if __name__ == '__main__':
    main(sys.argv[1])
