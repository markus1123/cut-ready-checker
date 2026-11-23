"""Retired held-out sets (faults/retired_v*.py). Each was scored blind once, then its misses were studied, so it now
counts as practice. Loaded automatically: adding retired_v3.py needs no edit here."""
import glob, importlib, os

FAULTS = []
for _f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), 'retired_v*.py'))):
    FAULTS += importlib.import_module('faults.' + os.path.basename(_f)[:-3]).FAULTS
