#!/usr/bin/env python3
"""retrieval.jsonl -> candidates.jsonl in the pilot README schema.

`tokens` is the generator tokenizer's count of the document text exactly as upstream
`GeneralODEX.get_prompt` inserts it (`ctx["text"]`, no special tokens). Separators and the
instruction line are not included here; run_manifest.py measures the full context.
Original text, title, score and the index fingerprint are kept alongside.
"""
import argparse

import odex_adapter as oa


def normalize(retrieval_rows, count_tokens, tokenizer_id):
    out = []
    for r in retrieval_rows:
        docs = sorted(r['docs'], key=lambda d: d['rank'])
        if [d['rank'] for d in docs] != list(range(1, len(docs) + 1)):
            raise ValueError(f"ranks must be 1..n for {r['task_id']}")
        if len({d['id'] for d in docs}) != len(docs):
            raise ValueError(f"duplicate doc ids for {r['task_id']}")
        out.append({
            'task_id': r['task_id'], 'dataset': r['dataset'], 'group': r['group'],
            'index_fingerprint': r['index_fingerprint'], 'tokenizer': tokenizer_id,
            'docs': [{'id': d['id'], 'rank': d['rank'], 'tokens': count_tokens(d['text']), 'score': d['score'],
                      'title': d['title'], 'text': d['text']} for d in docs],
        })
    return out


def main():
    ap = argparse.ArgumentParser(description='Normalize retrieval output to candidates.jsonl')
    ap.add_argument('--retrieval', required=True)
    ap.add_argument('--model-dir', required=True, help='local generator snapshot (tokenizer)')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True)
    rows = normalize(oa.read_jsonl(args.retrieval), lambda t: len(tok(t, add_special_tokens=False)['input_ids']),
                     tok.name_or_path)
    oa.write_jsonl(args.out, rows)
    print(f'wrote {len(rows)} tasks -> {args.out}')


if __name__ == '__main__':
    main()
