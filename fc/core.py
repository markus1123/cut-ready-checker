"""Fault + Finding types, rule registry and the catch-rate scoreboard."""
import importlib, json, os, pkgutil, time, traceback
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Fault:
    id: str
    title: str
    why: str = ''                      # what goes wrong in the workshop if it is not caught
    params: Optional[Callable] = None  # mutate (P, S) before the generator runs  (designer / input error)
    parts: Optional[Callable] = None   # mutate (parts, asm, info) after build()   (generator bug)
    dxf: Optional[Callable] = None     # mutate {filename: dxf text} after writing   (file / export bug)
    source: str = ''                   # where the failure mode comes from
    good: bool = False                 # True = a known-GOOD variant: must produce no errors (false-positive guard)


@dataclass
class Finding:
    rule: str
    severity: str        # 'error' (stops cutting) or 'warn'
    msg: str
    part: str = ''


RULES = {}


def rule(rule_id, desc):
    def deco(fn):
        fn.rule_id, fn.desc = rule_id, desc
        RULES[rule_id] = fn
        return fn
    return deco


def load_rules():
    from . import rules as pkg
    for m in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module('fc.rules.' + m.name)
    return RULES


def run_rules(d, only=None):
    out = []
    for rid, fn in sorted(load_rules().items()):
        if only and rid not in only:
            continue
        try:
            out += fn(d) or []
        except Exception as e:  # a crashing rule is a finding about the rule, never a silent pass
            out.append(Finding(rid, 'crash', '%s: %s' % (type(e).__name__, e)))
    return out


def gen_errors(d):
    """The generator's own verdict: errors + blocks in rapport.txt."""
    return list(d.gen.err) + list(d.gen.block)


def verdict(d, rules=True):
    """(caught?, messages). Caught = the design would be stopped before cutting."""
    msgs = ['gen: ' + m for m in gen_errors(d)]
    if rules:
        msgs += ['%s: %s' % (f.rule, f.msg) for f in run_rules(d) if f.severity in ('error', 'crash')]
    return bool(msgs), msgs
