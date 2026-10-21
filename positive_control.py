#!/usr/bin/env python3
"""Positive control for a finished run: feed each row's upstream prompt + the ODEX reference
solution (+ a stop word) through the same upstream postprocess_generation and the same
sandboxed official evaluator that run_manifest.py used. All should pass; if they do, a 0%
model pass rate is a model outcome, not a pipeline defect. Not model output; not a result.
"""
import argparse
import json
import os

import odex_adapter as oa
import sandbox_eval


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--upstream', required=True)
    ap.add_argument('--sandbox-python', required=True)
    ap.add_argument('--subsets', nargs='*', default=['none', 'r1+r2', 'r2+r3'])
    ap.add_argument('--eos', default='<|endoftext|>')
    args = ap.parse_args()
    os.environ['CRAG_UPSTREAM'] = args.upstream
    path = os.path.join(args.run_dir, 'rag_inputs.jsonl')
    rag = oa.read_jsonl(path)
    task = oa.upstream_odex_task(path, 5)
    task.stop_words.append(args.eos)
    ds = task.get_dataset()
    progs = []
    for i, r in enumerate(rag):
        if r['crag_subset_key'] not in args.subsets:
            continue
        prompt = task.get_prompt(ds[i])
        prog = task.postprocess_generation(prompt + r['canonical_solution'] + r['suffix'] + '\ndef junk', i,
                                           new_tokens_only=False)
        progs.append({'key': f"{r['crag_task_id']}|{r['crag_subset_key']}", 'candidate': prog,
                      'reference': task.get_reference(ds[i])})
    res, _ = sandbox_eval.evaluate(progs, args.sandbox_python, args.upstream)
    out = {'passed': sum(v['passed'] for v in res.values()), 'total': len(res), 'rows': res}
    with open(os.path.join(args.run_dir, 'positive_control.json'), 'w') as f:
        json.dump(out, f, indent=1)
    print(f"positive control passed {out['passed']}/{out['total']}")


if __name__ == '__main__':
    main()
