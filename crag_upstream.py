"""Import pieces of the official CodeRAG-Bench `generation/eval` package without editing it.

`generation/eval/tasks/__init__.py` eagerly imports every task (SWE-bench needs GitPython,
RepoEval needs extra deps, ...). We register empty package shells for `eval`, `eval.tasks`
and `eval.tasks.custom_metrics` whose `__path__` points at the upstream directories, so
`import eval.tasks.odex` loads the real upstream module files but skips the package
`__init__` side effects. No upstream source is copied or patched.
"""
import importlib
import os
import subprocess
import sys
import types
from pathlib import Path

PINNED_SHA = 'f9e100ca9ed94b8f1983b356ae81966e30210cf4'


def upstream_root():
    p = os.environ.get('CRAG_UPSTREAM')
    if not p:
        raise RuntimeError('Set CRAG_UPSTREAM to a code-rag-bench checkout at ' + PINNED_SHA)
    return Path(p).resolve()


def upstream_sha(root=None):
    root = root or upstream_root()
    return subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True,
                          check=True).stdout.strip()


def upstream_dirty(root=None):
    root = root or upstream_root()
    out = subprocess.run(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=no'],
                         capture_output=True, text=True, check=True).stdout
    return bool(out.strip())


def _register(root):
    gen = root / 'generation'
    for name, path in [('eval', gen / 'eval'), ('eval.tasks', gen / 'eval' / 'tasks'),
                       ('eval.tasks.custom_metrics', gen / 'eval' / 'tasks' / 'custom_metrics')]:
        mod = sys.modules.get(name)
        if mod is None or getattr(mod, '__crag_shell__', False) is False:
            mod = types.ModuleType(name)
            mod.__path__ = [str(path)]
            mod.__crag_shell__ = True
            sys.modules[name] = mod


def load(module, root=None):
    """e.g. load('eval.tasks.odex') or load('eval.tasks.custom_metrics.code_eval')."""
    _register(Path(root) if root else upstream_root())
    return importlib.import_module(module)
