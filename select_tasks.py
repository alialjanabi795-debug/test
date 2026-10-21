#!/usr/bin/env python3
"""Pick the ODEX-en pilot slice by a fixed rule (see odex_adapter.select_tasks) and,
optionally, keep only tasks whose upstream reference solution passes the official
evaluator inside the sandbox (equivalent of `main.py --check_references`)."""
import argparse
import json

import odex_adapter as oa


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--odex', required=True)
    ap.add_argument('--canonical', required=True, help='upstream retrieval/datasets/canonical/odex_docs.json')
    ap.add_argument('--n', type=int, default=8)
    ap.add_argument('--verify-references', action='store_true')
    ap.add_argument('--python', help='sandbox interpreter (required with --verify-references)')
    ap.add_argument('--upstream', help='code-rag-bench checkout (required with --verify-references)')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    odex = oa.load_odex(args.odex)
    canon = oa.read_jsonl(args.canonical)
    # Over-select so reference failures can be dropped without changing the rule.
    keys, _ = oa.select_tasks(odex, canon, args.n * 3 if args.verify_references else args.n)
    report = {'rule': 'library subset of stdlib, no side-effect libs, >=1 canonical doc, file order',
              'side_effect_libs': sorted(oa.SIDE_EFFECT_LIBS), 'candidates_in_order': keys}
    if args.verify_references:
        import tempfile
        import sandbox_eval
        with tempfile.TemporaryDirectory() as d:
            path = f'{d}/refcheck.jsonl'
            oa.write_jsonl(path, [dict(odex[k], docs=[]) for k in keys])
            task = oa.upstream_odex_task(path, topk_docs=0)
            ds = task.get_dataset()
            # Upstream prompt (no context) + reference body, scored with upstream get_reference.
            progs = [{'key': k, 'candidate': task.get_prompt(ds[i], return_dict=True)['prompt']
                      + odex[k]['canonical_solution'] + odex[k]['suffix'], 'reference': task.get_reference(ds[i])}
                     for i, k in enumerate(keys)]
        res, _ = sandbox_eval.evaluate(progs, args.python, args.upstream)
        report['reference_check'] = {k: res[k] for k in keys}
        keys = [k for k in keys if res[k]['passed']]
    keys = keys[:args.n]
    report['selected'] = keys
    json.dump(keys, open(args.out, 'w'), indent=1)
    json.dump(report, open(args.out.replace('.json', '') + '_selection_report.json', 'w'), indent=1)
    print(f'selected {len(keys)} tasks -> {args.out}')


if __name__ == '__main__':
    main()
