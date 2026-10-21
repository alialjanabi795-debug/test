#!/usr/bin/env python3
"""Frozen BM25 retrieval for selected ODEX-en tasks, mirroring upstream
`retrieval/eval_beir_okapibm25.py`: rank_bm25.BM25Okapi over the docprompting-conala doc
pool (built as in `retrieval/create/odex.py`: _id=str(i), title=doc_id, text=doc_content),
whitespace tokenization (`str.split(" ")`), query = ODEX `intent`.

Differences from upstream, all deliberate and recorded: we keep corpus ids and BM25 scores
(upstream's results file drops them), ties are broken by corpus order (upstream's stable
sort over dict order gives the same), and we skip upstream's unrelated SentenceBERT
evaluator load.
"""
import argparse
import hashlib
import json
import platform

import numpy as np

import odex_adapter as oa


def load_corpus(path):
    docs = []
    for i, r in enumerate(oa.read_jsonl(path)):
        docs.append({'id': str(i), 'title': r['doc_id'], 'text': r['doc_content']})
    return docs


def fingerprint(corpus_path, extra):
    h = hashlib.sha256()
    h.update(oa.sha256_file(corpus_path).encode())
    h.update(json.dumps(extra, sort_keys=True).encode())
    return h.hexdigest()


def retrieve(bm25, docs, query, topn):
    scores = np.asarray(bm25.get_scores(query.split(' ')), dtype=float)
    order = sorted(range(len(docs)), key=lambda i: (-scores[i], i))[:topn]
    return [dict(docs[i], rank=r + 1, score=float(scores[i])) for r, i in enumerate(order)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--odex', required=True, help='neulab/odex en_test.jsonl (pinned revision)')
    ap.add_argument('--corpus', required=True, help='neulab/docprompting-conala conala-docs.jsonl')
    ap.add_argument('--tasks', required=True, help='JSON list of task keys (from select_tasks.py)')
    ap.add_argument('--topn', type=int, default=5)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    import rank_bm25
    from importlib.metadata import version

    odex = oa.load_odex(args.odex)
    keys = json.load(open(args.tasks))
    docs = load_corpus(args.corpus)
    bm25 = rank_bm25.BM25Okapi([d['text'].split(' ') for d in docs])
    meta = {'retriever': 'rank_bm25.BM25Okapi', 'rank_bm25': version('rank_bm25'), 'k1': bm25.k1, 'b': bm25.b,
            'epsilon': bm25.epsilon, 'tokenizer': 'str.split(" ")', 'query_field': 'intent',
            'corpus_size': len(docs), 'corpus_sha256': oa.sha256_file(args.corpus), 'numpy': np.__version__,
            'python': platform.python_version()}
    fp = fingerprint(args.corpus, meta)
    rows = []
    for k in keys:
        rec = odex[k]
        rows.append({'task_id': k, 'dataset': oa.DATASET, 'group': oa.group_of(rec), 'query': rec['intent'],
                     'docs': retrieve(bm25, docs, rec['intent'], args.topn), 'index_fingerprint': fp,
                     'retrieval_meta': meta})
    oa.write_jsonl(args.out, rows)
    print(f'retrieved top-{args.topn} for {len(rows)} tasks; index_fingerprint={fp}')


if __name__ == '__main__':
    main()
