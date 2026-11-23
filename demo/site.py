#!/usr/bin/env python3
"""Build the public static site into site/: index.html (demo page + 3D hero) and chest.html (3D viewer).
    python3 demo/build.py && python3 demo/site.py      then deploy the site/ folder (Netlify / Cloudflare Pages)."""
import json, os, shutil
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
if (true) {   // public site: always the clean, English embed
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
TR = r'''
const PART_EN = { A: 'Top', B: 'Bottom', BEIN: 'Leg', C: 'Left side', CH: 'Right side', D: 'Middle wall', E1: 'Drawer box, front end',
  E2: 'Drawer box, back end', G: 'Back panel', H: 'Plinth strip', K: 'Drawer front', S: 'Drawer side, left', SH: 'Drawer side, right',
  SB: 'Drawer bottom', skinne: 'Slide', 'Håndtak': 'Handle' };
function trLabel(l) {
  const m = String(l).match(/^(\S+)(?:\s+(?:venstre|høyre|front))?(?:\s+(\d+)([HV]))?/);
  if (!m) return l;
  const n = PART_EN[m[1]] || l;
  return m[2] ? n + ' · row ' + m[2] + ', ' + (m[3] === 'V' ? 'left' : 'right') + ' column' : n;
}
'''
assert 'tip.textContent = `${a.label}' in v
v = v.replace('tip.textContent = `${a.label}', 'tip.textContent = `${trLabel(a.label)}')
v = v.replace("import * as THREE from 'three';", "import * as THREE from 'three';" + TR, 1)
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
  </section>
"""
p = p.replace('    <div class="stats" id="stats"></div>\n  </header>\n', '    <div class="stats" id="stats"></div>\n  </header>\n' + HERO, 1)
p = p.replace('<title>Cut-Ready Checker</title>', '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Cut-Ready Checker</title>\n<meta name="description" content="A self-improving checker that stops bad CNC cutting files for flat-pack furniture before they reach the router.">', 1)
# --- second product with the same method: RN-1 radio relay enclosure (../field-radio-foundry) at /radio/
RADIO = os.path.join(HERE, '..', 'field-radio-foundry')
if os.path.isdir(os.path.join(RADIO, 'web')):
    dst = os.path.join(OUT, 'radio')
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(os.path.join(RADIO, 'web'), dst)
    shutil.copy(os.path.join(RADIO, 'index.html'), os.path.join(dst, 'plan.html'))
    sc = [json.loads(l) for l in open(os.path.join(RADIO, 'score_history.jsonl'))][-1]
    pc = lambda k: '%d/%d' % (sc[k + '_caught'], sc[k + '_n'])
    RADIO_SEC = f"""
  <section>
    <div class="head"><div class="eyebrow">Same method, another product</div><h2>RN-1: a rugged radio relay enclosure</h2>
      <p class="mute">The same loop on a different object: a printed IP67 box for a mesh-radio relay node (gasket groove, heat-set inserts, sealed button, antenna port, battery). Faults are injected at three layers (input values, generator maths, exported solids) and scored on train, mined and blind held-out sets. Current score: train {pc('train')}, mined {pc('mined')}, held-out {pc('heldout')}, false alarms {sc['false_pos']}/{sc['good_n']}, {sc['rules']} rules.</p>
      <p><a href="radio/">3D model, drawings and checks →</a> &nbsp;·&nbsp; <a href="radio/plan.html">Project plan →</a></p></div>
  </section>
"""
    p = p.replace(HERO, HERO + RADIO_SEC, 1)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(p)
print('wrote', OUT)
