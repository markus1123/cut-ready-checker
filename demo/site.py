#!/usr/bin/env python3
"""Build the public static site into site/: index.html (demo page + 3D hero) and chest.html (3D viewer).
    python3 demo/build.py && python3 demo/site.py      then deploy the site/ folder (Netlify / Cloudflare Pages)."""
import os, shutil
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN_UT = os.path.join(HERE, '..', 'kommode-bestilling', 'generator', 'ut', 'forhandsvisning.html')
OUT = os.path.join(HERE, 'site')
os.makedirs(OUT, exist_ok=True)

# --- 3D viewer with an embed mode (?embed): only the explode / open controls, English labels, a short intro animation
v = open(GEN_UT, encoding='utf-8').read()
EMBED_CSS = """
  html.embed #st, html.embed #ctl > :not(.keep) { display:none !important; }
  html.embed #ctl { width:auto; right:auto; max-width:280px; }
  html.embed, html.embed body { background:transparent; }
</style>"""
v = v.replace('</style>', EMBED_CSS, 1)
v = v.replace('<h1>Kommode – 3D</h1>', '<h1 class="keep">Kommode – 3D</h1>')
v = v.replace('<label>Sprengskisse', '<label class="keep">Sprengskisse').replace('<label>Alle skuffer ut', '<label class="keep">Alle skuffer ut')
v = v.replace('<div style="display:flex;gap:6px;margin-top:6px">', '<div class="keep" style="display:flex;gap:6px;margin-top:6px">', 1)
v = v.replace('<canvas id="c"></canvas>', """<canvas id="c"></canvas>
<script>
if (/[?&]embed/.test(location.search)) {
  document.documentElement.classList.add('embed');
  addEventListener('DOMContentLoaded', () => {
    const t = (sel, s) => { const el = document.querySelector(sel); if (el) el.firstChild.textContent = s; };
    document.querySelector('#ctl h1').textContent = 'Drag to rotate · scroll to zoom';
    document.querySelector('#ex').parentNode.firstChild.textContent = 'Explode ';
    document.querySelector('#op').parentNode.firstChild.textContent = 'Open drawers ';
    document.querySelector('#ctr').textContent = 'Recenter'; document.querySelector('#cls').textContent = 'Close all';
  });
  addEventListener('load', () => {            // intro: explode out and back once
    const ex = document.querySelector('#ex'); if (!ex) return;
    const t0 = performance.now(), D = 3200;
    (function step(now) {
      const k = Math.min(1, (now - t0) / D), v = Math.sin(Math.PI * k) * 0.75;
      ex.value = v; ex.dispatchEvent(new Event('input', { bubbles: true }));
      if (k < 1) requestAnimationFrame(step);
    })(t0 + 1);
  });
}
</script>""", 1)
open(os.path.join(OUT, 'chest.html'), 'w', encoding='utf-8').write(v)

# --- main page with a 3D hero right under the header
p = open(os.path.join(HERE, 'demo', 'index.html'), encoding='utf-8').read()
HERO = """
  <section>
    <div class="head"><div class="eyebrow">The object</div><h2>An 8-drawer chest, generated from 30 numbers</h2>
      <p class="mute">This is the generator's own 3D model, built from the same parts list that becomes the cutting files. Drag to rotate, pull the sliders to explode it or open the drawers, click a drawer to open it. Every part you see is checked by the rules below before it can reach the router.</p></div>
    <div class="card" style="overflow:hidden;position:relative">
      <iframe src="chest.html?embed" title="3D model of the chest of drawers" loading="lazy" style="display:block;width:100%;height:min(72vh,620px);border:0"></iframe>
    </div>
    <p class="mute" style="font-size:13px"><a href="chest.html" style="color:var(--accent)">Open the full viewer</a> – materials, prices per sheet and the generator's own checks (in Norwegian).</p>
  </section>
"""
p = p.replace('    <div class="stats" id="stats"></div>\n  </header>\n', '    <div class="stats" id="stats"></div>\n  </header>\n' + HERO, 1)
p = p.replace('<title>Cut-Ready Checker</title>', '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Cut-Ready Checker</title>\n<meta name="description" content="A self-improving checker that stops bad CNC cutting files for flat-pack furniture before they reach the router.">', 1)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(p)
print('wrote', OUT)
