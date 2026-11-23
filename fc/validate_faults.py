"""Check that a fault set is well-formed WITHOUT revealing what the checker says about it.

    python3 -m fc.validate_faults heldout2

Per fault prints: ok | crash (with the error) | inert (the design files are identical to the unfaulted design).
Never prints generator or rule verdicts, so a red-team author can use it without learning the checker."""
import glob, hashlib, os, sys, traceback
from . import design
from .score import load_set


def digest(d):
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(d.out, '*.dxf')) + glob.glob(os.path.join(d.out, '*.csv')) + glob.glob(os.path.join(d.out, '*.json'))):
        h.update(os.path.basename(f).encode()); h.update(open(f, 'rb').read())
    return h.hexdigest()


def main():
    name = sys.argv[1]
    base = design.make()
    try:
        b = digest(base)
    finally:
        design.cleanup(base)
    bad = 0
    for f in load_set(name):
        try:
            d = design.make(fault=f)
            try:
                st = 'inert' if digest(d) == b else 'ok'
            finally:
                design.cleanup(d)
        except Exception as e:
            st = 'crash  %s: %s' % (type(e).__name__, str(e)[:200])
        bad += st != 'ok'
        print('%-5s %-6s %s' % (f.id, st.split()[0], f.title if st == 'ok' else st))
    print('%d faults, %d problems' % (len(load_set(name)), bad))


if __name__ == '__main__':
    main()
