#!/usr/bin/env python3
"""Generate bounded evidence-subset assignments, without model inference."""
import argparse
import itertools
import json
from pathlib import Path


def read_jsonl(path):
    for n, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        if line.strip():
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f'{path}:{n}: {e}') from e


def generate(tasks, topn=5, max_docs=2, budget=4096):
    if max_docs < 1 or topn < 1 or budget < 1:
        raise ValueError('topn, max_docs and budget must be positive')
    seen_tasks = set()
    for task in tasks:
        for k in ('task_id','dataset','group','docs'):
            if k not in task:
                raise ValueError(f'Task missing field: {k}')
        key = (task['dataset'], task['task_id'])
        if key in seen_tasks:
            raise ValueError(f'Duplicate task: {key}')
        seen_tasks.add(key)
        docs = sorted(task['docs'], key=lambda d: d['rank'])[:topn]
        if not docs or len({d['id'] for d in docs}) != len(docs):
            raise ValueError(f'No docs or duplicate doc IDs for {key}')
        if len({d['rank'] for d in docs}) != len(docs):
            raise ValueError(f'Duplicate document rank for {key}')
        for d in docs:
            if not isinstance(d['tokens'], int) or d['tokens'] <= 0:
                raise ValueError(f'Bad token count for {key}: {d}')
        allowed = []
        for size in range(0, min(max_docs, len(docs))+1):
            for c in itertools.combinations(range(len(docs)), size):
                toks = sum(docs[i]['tokens'] for i in c)
                if toks <= budget:
                    allowed.append((c, toks))
        # Top-k: first two documents that fit, in retrieval order; not a learned selector.
        topk = []
        for i, d in enumerate(docs):
            if len(topk) >= max_docs:
                break
            if sum(docs[j]['tokens'] for j in topk) + d['tokens'] <= budget:
                topk.append(i)
        topk_key = '+'.join(f'r{i+1}' for i in topk) if topk else 'none'
        for c, tokens in allowed:
            subset_key = '+'.join(f'r{i+1}' for i in c) if c else 'none'
            yield {
                'task_id': task['task_id'], 'dataset': task['dataset'],
                'group': task['group'], 'subset_key': subset_key,
                'doc_ids': [docs[i]['id'] for i in c],
                'candidate_doc_ids': [d['id'] for d in docs],
                'context_tokens': tokens, 'token_budget': budget,
                'max_docs': max_docs, 'topk_subset_key': topk_key,
                'type': 'empty' if not c else 'single' if len(c)==1 else 'pair' if len(c)==2 else 'larger',
            }


def main():
    ap = argparse.ArgumentParser(description='Prepare legal evidence subsets from normalized candidate files')
    ap.add_argument('--candidates', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--budget', type=int, default=4096)
    ap.add_argument('--topn', type=int, default=5)
    ap.add_argument('--max-docs', type=int, default=2)
    args = ap.parse_args()
    records = list(generate(read_jsonl(args.candidates), args.topn, args.max_docs, args.budget))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'Prepared {len(records)} legal subsets for {len(set((r["dataset"],r["task_id"]) for r in records))} tasks => {args.out}')

if __name__ == '__main__':
    main()
