"""Load archived policy/selection code without its unused local downloader import.

run_eval.py imports an ignored, unreleased DocLayNet downloader unconditionally.
Only that import is omitted in memory. All policy and surname-selection function
bodies execute unchanged from their committed source files. No source is edited.
"""
import ast
import importlib
import sys
import types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def load():
    path=ROOT/'research/realworld_e1_eval/run_eval.py'
    tree=ast.parse(path.read_text(),filename=str(path))
    omitted=[n for n in tree.body if isinstance(n,ast.Import) and any(a.name=='download_sample' for a in n.names)]
    assert len(omitted)==1 and len(omitted[0].names)==1
    tree.body=[n for n in tree.body if n not in omitted]
    module=types.ModuleType('run_eval');module.__file__=str(path)
    sys.modules['run_eval']=module
    exec(compile(tree,str(path),'exec'),module.__dict__)
    sys.path.insert(0,str(path.parent))
    generic_attacker=importlib.import_module('run_generic_attacker')
    sys.path.insert(0,str(ROOT/'research/funsd_validation'))
    real=importlib.import_module('funsd_real')
    return module,generic_attacker,real
