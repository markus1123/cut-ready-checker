"""Rule registry for geometry-only rules (any designer's DXF). Rules: fn(g: GDesign) -> iterable of Finding."""
import importlib, pkgutil, traceback
from fc.core import Finding

GX_RULES = {}


def gx_rule(rule_id, desc):
    def deco(fn):
        fn.rule_id, fn.desc = rule_id, desc
        GX_RULES[rule_id] = fn
        return fn
    return deco


def load_rules():
    from . import rules as pkg
    for m in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(pkg.__name__ + '.' + m.name)
    return GX_RULES


def run(g):
    """-> (findings, crashed_rule_ids). A crashing rule finds nothing but is reported (robustness gate)."""
    out, crashed = [], []
    for rid, fn in sorted(load_rules().items()):
        try:
            for f in fn(g) or []:
                f.rule = f.rule or rid
                out.append(f)
        except Exception:
            crashed.append(rid)
    return out, crashed


def error_keys(findings):
    """What counts as 'flagged': error findings, keyed by rule + part (so a mutant must add a NEW one to count)."""
    return {(f.rule, f.part) for f in findings if f.severity == 'error'}
