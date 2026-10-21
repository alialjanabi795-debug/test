"""Executed INSIDE the sandbox only. Scores programs with the official ODEX metric.

argv: <upstream_root> <job_dir>. Reads <job_dir>/programs.json:
  [{"key": str, "candidate": str, "reference": str}, ...]
Writes <job_dir>/exec_results.json: [{"key", "passed", "result"}, ...]
Each program is passed to upstream `compute_code_eval` as its own problem with one
candidate, so `passed` is that candidate's own test outcome (pass@1 with n=1).
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crag_upstream  # noqa: E402


def main():
    root, job = Path(sys.argv[1]), Path(sys.argv[2])
    timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    os.environ['HF_ALLOW_CODE_EVAL'] = '1'
    code_eval = crag_upstream.load('eval.tasks.custom_metrics.code_eval', root)
    progs = json.loads((job / 'programs.json').read_text())
    _, results = code_eval.compute_code_eval(
        predictions=[[p['candidate']] for p in progs], references=[p['reference'] for p in progs],
        k=[1], num_workers=workers, timeout=timeout)
    out = []
    for i, p in enumerate(progs):
        (_, r), = results[i]
        out.append({'key': p['key'], 'passed': bool(r['passed']), 'result': r['result']})
    (job / 'exec_results.json').write_text(json.dumps(out))


if __name__ == '__main__':
    main()
