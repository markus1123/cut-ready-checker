"""Build a design (optionally with a seeded fault) by running the real generator, and load what it wrote."""
import copy, importlib, json, os, sys, tempfile, shutil, glob, contextlib, io

GEN = os.environ.get('FC_GEN') or os.path.join(os.path.dirname(__file__), '..', '..', 'kommode-bestilling', 'generator')
GEN = os.path.abspath(GEN)
if GEN not in sys.path:
    sys.path.insert(0, GEN)
import kommode  # noqa: E402
from . import dxfread  # noqa: E402

# A plausible "ready" state: boards measured, workshop confirmed, a slide bought and measured.
# (Values are realistic stand-ins, not the user's real measurements.)
READY_SLIDE = dict(verifisert=True, korpus_hull=[[37, 0], [165, 0], [357, 0]],
                   korpus_hull_alternativ=[[69, 0], [197, 0], [389, 0]], skuff_hull=[[35, 0], [163, 0]])
READY_THK = {'korpus': 18.8, 'front': 18.8, 'skuff': 18.8, 'skuffebunn': 5.9, 'bakplate': 3.0}


def base(ready=True):
    """Nominal params + slide spec from the generator folder, optionally put in the 'ready to cut' state."""
    with contextlib.redirect_stdout(io.StringIO()):
        P, S = kommode.load()
    P, S = copy.deepcopy(P), copy.deepcopy(S)
    if ready:
        P['verksted']['bekreftet'] = True
        P['tykkelse_malt'].update(READY_THK)
        P['tykkelse_malt']['malt'] = True
        S.update(copy.deepcopy(READY_SLIDE))
        for m in P['_valg'].values():
            m['pris'] = m['pris'] or m['pris_anslag']
    return P, S


class Design:
    """Everything the checker may look at. parts/asm/info = generator model, sheets = parsed DXFs on disk."""
    def __init__(s, P, S, parts, asm, info, report, out):
        s.P, s.S, s.parts, s.asm, s.info, s.gen, s.out = P, S, parts, asm, info, report, out
        s.by = {p['code']: p for p in parts}
        s.summary = json.load(open(os.path.join(out, 'oppsummering.json')))
        s.sheets = [dxfread.read(f) for f in sorted(glob.glob(os.path.join(out, '*.dxf')))]
        s.kit_sheets = [dxfread.read(f) for f in sorted(glob.glob(os.path.join(out, 'prove', '*.dxf')))]
        s.files = {os.path.basename(f): open(f, encoding='utf-8-sig').read()
                   for f in glob.glob(os.path.join(out, '*.csv'))}


def make(P=None, S=None, fault=None, keep=None):
    """Run the generator (with the fault's mutations) into a temp dir and return a Design."""
    if P is None:
        P, S = base()
    P, S = copy.deepcopy(P), copy.deepcopy(S)
    if fault and fault.params:
        fault.params(P, S)
    out = keep or tempfile.mkdtemp(prefix='fc_')
    orig = kommode.build
    if fault and fault.parts:
        def build(P_, S_):
            parts, asm, info = orig(P_, S_)
            fault.parts(parts, asm, info)
            return parts, asm, info
        kommode.build = build
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            R, _ = kommode.run(P, S, out)
        parts, asm, info = kommode.build(P, S)
    finally:
        kommode.build = orig
    if fault and fault.dxf:
        files = {f: open(f).read() for f in glob.glob(os.path.join(out, '*.dxf'))}
        named = {os.path.basename(k): v for k, v in files.items()}
        fault.dxf(named)
        for k in files:
            open(k, 'w').write(named[os.path.basename(k)])
    d = Design(P, S, parts, asm, info, R, out)
    if not keep:
        d._tmp = out
    return d


def cleanup(d):
    if getattr(d, '_tmp', None):
        shutil.rmtree(d._tmp, ignore_errors=True)
