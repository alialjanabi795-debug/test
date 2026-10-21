"""Host side: score candidate programs with the official evaluator inside `sandbox.run`."""
import json
import os
import shutil
import tempfile
from pathlib import Path

import sandbox

HERE = Path(__file__).resolve().parent
PAYLOAD = ['crag_upstream.py', 'sandbox_eval_runner.py']


def evaluate(programs, python, upstream_root, per_test_timeout=3.0, workers=4, wall_timeout_s=900, limits=None):
    """programs: [{"key","candidate","reference"}]. Returns ({key: {"passed","result"}}, log dict).

    Read-only inside the sandbox: interpreter prefix (must live outside /root,/home,/tmp),
    the upstream checkout and this runner payload. Writable: the job dir holding programs.json
    and exec_results.json. Candidate code runs in a child of the evaluator process (upstream
    design), so it could in principle overwrite exec_results.json; the key-set check below
    catches gross tampering, not a deliberate forgery.
    """
    keys = [p['key'] for p in programs]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate program keys')
    with tempfile.TemporaryDirectory() as payload, tempfile.TemporaryDirectory() as job:
        os.chmod(payload, 0o755)  # readable by the sandbox's nobody user
        for f in PAYLOAD:
            shutil.copy2(HERE / f, Path(payload, f))
            os.chmod(Path(payload, f), 0o644)
        # ro/0 = upstream, ro/1 = payload
        ro_up, ro_pay = sandbox.RO_MOUNT / '0', sandbox.RO_MOUNT / '1'
        argv = [python, '-I', str(ro_pay / 'sandbox_eval_runner.py'), str(ro_up), str(sandbox.JOB_MOUNT),
                str(per_test_timeout), str(workers)]
        # The runner reads programs.json from the job dir; copy it there (job is the only rw dir).
        Path(job, 'programs.json').write_text(json.dumps(programs))
        proc = sandbox.run(argv, job, ro_binds=[upstream_root, payload], timeout_s=wall_timeout_s, limits=limits)
        log = {'returncode': proc.returncode, 'stdout_tail': proc.stdout[-4000:], 'stderr_tail': proc.stderr[-4000:]}
        out = Path(job, 'exec_results.json')
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(f'sandboxed evaluation failed: {log}')
        res = json.loads(out.read_text())
    got = {r['key']: {'passed': r['passed'], 'result': r['result']} for r in res}
    if sorted(got) != sorted(keys) or any(type(v['passed']) is not bool for v in got.values()):
        raise RuntimeError('evaluator output does not match submitted programs')
    return got, log
