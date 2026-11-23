#!/usr/bin/env python3
"""Strip local-file and command references from the public site (site/). The site is a shared demo page,
so visible text and page source must not mention script names, local paths or how to run things.

    python3 demo/public_clean.py [site_dir]     # run after demo/site.py (site.py calls it at the end)
Exits non-zero if anything that looks local is left.
"""
import os, re, sys

SITE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'site')

REPLACE = {
    'index.html': [
        ("Run python3 optimize.py to fill this chart.", "No optimizer runs recorded yet."),
    ],
    'chest.html': [
        ("//      The nesting below is a line-for-line port of nestlib.py (split_sheet, Bin, _pack1, pack, plan),\n"
         "//      so the numbers match what `python3 kommode.py` writes for the same choice.",
         "//      The nesting below is a line-for-line port of the generator's sheet nesting,\n"
         "//      so the numbers match the generator's output for the same choice."),
        ("Sjekk av lagret plan (params.json)", "Sjekk av lagret plan"),
        ("Samme som lagret plan i params.json.", "Samme som lagret plan."),
        (re.compile(r'\s*<p class="sub"[^>]*>Erstatt "materialvalg" i params\.json[^<]*<code>[^<]*</code>\.</p>'), ""),
    ],
}

LOCAL = re.compile(r'python3? |\.venv|\b[\w-]+\.py\b|\.jsonl\b|~/|/Users/|Downloads|localhost|params\.json|claude\.ai/(?:code/)?artifact')


def main():
    left = []
    for root, _, files in os.walk(SITE):
        for name in files:
            if not name.endswith(('.html', '.json')):
                continue
            path = os.path.join(root, name)
            s = open(path, encoding='utf-8').read()
            new = s
            for old, rep in REPLACE.get(os.path.relpath(path, SITE), []):
                new = old.sub(rep, new) if hasattr(old, 'sub') else new.replace(old, rep)
            if new != s:
                open(path, 'w', encoding='utf-8').write(new)
            for m in LOCAL.finditer(new):
                left.append('%s: ...%s...' % (os.path.relpath(path, SITE), re.sub(r'\s+', ' ', new[max(0, m.start() - 50):m.end() + 30])))
    for x in left:
        print('LOCAL REFERENCE LEFT', x)
    print('public_clean: %s' % ('clean' if not left else '%d references left' % len(left)))
    return 1 if left else 0


if __name__ == '__main__':
    sys.exit(main())
