#!/usr/bin/env python3
"""Generate and execution-evaluate every (manifest row x sample_id) with one frozen local model.

Per manifest row the prompt comes from the official `GeneralODEX.get_prompt`, fed with the
ODEX record plus exactly the selected documents, in retrieval-rank order; `none` rows get an
empty `docs` list (upstream no-retrieval prompt). Only the documents differ between subsets.
Programs are post-processed by the official `postprocess_generation` and scored by the
official `compute_code_eval` inside `sandbox.py`.

Nothing is truncated. A row is skipped (and written to skipped.jsonl with the reason) when
the measured context exceeds the manifest budget, or prompt + max_new_tokens exceeds the
model context window. Generation errors are recorded per sample, never turned into fails.

Outputs in --out-dir: results.jsonl, skipped.jsonl, run_config.json, rag_inputs.jsonl,
raw/generations.jsonl (prompt, raw continuation, program), raw/evaluations.jsonl,
raw/eval_logs.jsonl. Re-running resumes from raw/*.jsonl.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import odex_adapter as oa

UPSTREAM_DEFAULTS = {'do_sample': True, 'temperature': 0.2, 'top_p': 0.95, 'top_k': 0}  # eval/arguments.py


def sample_key(dataset, task_id, subset_key, sample_id):
    return f'{dataset}|{task_id}|{subset_key}|{sample_id}'


def load_raw(path):
    return {r['key']: r for r in oa.read_jsonl(path)} if Path(path).exists() else {}


def append_jsonl(path, row):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


def build_rag_inputs(manifest, candidates, odex):
    """One upstream-schema row per manifest row: ODEX record + docs[{title,text}] (rank order)."""
    cand = {(c['dataset'], c['task_id']): c for c in candidates}
    rows = []
    for i, m in enumerate(manifest):
        c = cand.get((m['dataset'], m['task_id']))
        if c is None:
            raise ValueError(f"manifest task missing from candidates: {m['task_id']}")
        by_id = {d['id']: d for d in c['docs']}
        if m['candidate_doc_ids'] != [d['id'] for d in sorted(c['docs'], key=lambda d: d['rank'])][:len(m['candidate_doc_ids'])]:
            raise ValueError(f"candidate list mismatch for {m['task_id']}")
        docs = [by_id[d] for d in m['doc_ids']]
        if [d['rank'] for d in docs] != sorted(d['rank'] for d in docs):
            raise ValueError(f"doc_ids not in rank order: {m['task_id']} {m['subset_key']}")
        rec = {k: v for k, v in odex[m['task_id']].items()}
        rec.update(docs=[{'title': d['title'], 'text': d['text']} for d in docs], crag_row=i,
                   crag_task_id=m['task_id'], crag_subset_key=m['subset_key'])
        rows.append(rec)
    return rows


def prompt_checks(prompt, context, doc_texts):
    """Every selected document must appear verbatim, in order, inside the context."""
    pos = -1
    for t in doc_texts:
        nxt = context.find(t, pos + 1)
        if nxt < 0 or nxt <= pos:
            return 'selected document missing or out of order in prompt'
        pos = nxt
    if not prompt.startswith(context):
        return 'context is not a prefix of the prompt'
    return None


class HFGenerator:
    """Frozen local causal LM via transformers on CPU; safetensors only, no remote code."""

    def __init__(self, model_dir, threads=None):
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer
        if threads:
            torch.set_num_threads(threads)
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True, use_safetensors=True,
                                                          torch_dtype=torch.float32).eval()
        self.max_context = int(self.model.config.max_position_embeddings)
        self.eos_token = self.tok.eos_token
        self.info = {'transformers': transformers.__version__, 'torch': torch.__version__,
                     'torch_threads': torch.get_num_threads(), 'dtype': 'float32', 'device': 'cpu',
                     'max_position_embeddings': self.max_context, 'tokenizer_class': type(self.tok).__name__}

    def encode(self, text):
        # Same call upstream TokenizedDataset makes (default special-token handling), minus truncation.
        return self.tok(text)['input_ids']

    def count(self, text):
        return len(self.tok(text, add_special_tokens=False)['input_ids'])

    def decode(self, ids):
        return self.tok.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)

    def generate(self, input_ids, seed, params, stop_words):
        torch = self.torch
        from transformers import StoppingCriteria, StoppingCriteriaList
        start = len(input_ids)
        tok = self.tok

        class EndOfFunctionCriteria(StoppingCriteria):
            # Same logic as upstream eval/generation.py (that module cannot be imported:
            # it constructs an OpenAI client at import time).
            hit = False

            def __call__(self, ids, scores, **kw):
                done = all(any(s in g for s in stop_words) for g in tok.batch_decode(ids[:, start:]))
                EndOfFunctionCriteria.hit = done
                return done

        torch.manual_seed(seed)
        x = torch.tensor([input_ids])
        t0 = time.perf_counter()
        with torch.no_grad():
            out = self.model.generate(
                x, attention_mask=torch.ones_like(x), max_new_tokens=params['max_new_tokens'],
                do_sample=params['do_sample'], temperature=params['temperature'], top_p=params['top_p'],
                top_k=params['top_k'], pad_token_id=tok.pad_token_id or tok.eos_token_id,
                stopping_criteria=StoppingCriteriaList([EndOfFunctionCriteria()]))
        latency = time.perf_counter() - t0
        new = out[0, start:].tolist()
        reason = ('stop_word' if EndOfFunctionCriteria.hit else
                  'eos' if new and new[-1] == tok.eos_token_id else
                  'max_new_tokens' if len(new) >= params['max_new_tokens'] else 'other')
        return {'new_text': self.decode(new), 'generated_tokens': len(new), 'latency_s': latency,
                'stop_reason': reason}


def run(manifest, candidates, odex, gen, evaluate_fn, task_factory, out_dir, sample_ids, base_seed, params,
        model_meta, only_subsets=None, limit_tasks=None, log=print):
    out = Path(out_dir)
    (out / 'raw').mkdir(parents=True, exist_ok=True)
    if only_subsets:
        manifest = [m for m in manifest if m['subset_key'] in only_subsets]
    if limit_tasks:
        keep = list(dict.fromkeys(m['task_id'] for m in manifest))[:limit_tasks]
        manifest = [m for m in manifest if m['task_id'] in keep]
    rag_rows = build_rag_inputs(manifest, candidates, odex)
    rag_path = out / 'rag_inputs.jsonl'
    oa.write_jsonl(rag_path, rag_rows)
    topk = max([len(m['candidate_doc_ids']) for m in manifest] + [1])
    task = task_factory(rag_path, topk)
    ds = task.get_dataset()
    if len(ds) != len(rag_rows):
        raise RuntimeError('upstream dataset size differs from rag_inputs')
    stop_words = list(task.stop_words) + ([gen.eos_token] if gen.eos_token else [])
    if gen.eos_token and gen.eos_token not in task.stop_words:
        task.stop_words.append(gen.eos_token)  # upstream parallel_generations does the same

    gens_path, evals_path = out / 'raw' / 'generations.jsonl', out / 'raw' / 'evaluations.jsonl'
    gens, evals = load_raw(gens_path), load_raw(evals_path)
    skipped, results = [], []
    by_task = {}
    for i, m in enumerate(manifest):
        by_task.setdefault(m['task_id'], []).append(i)

    for task_id, idxs in by_task.items():
        pending = []
        for i in idxs:
            m, doc = manifest[i], ds[i]
            if doc['crag_row'] != i or doc['crag_subset_key'] != m['subset_key']:
                raise RuntimeError('row alignment broken')
            parts = task.get_prompt(doc, return_dict=True)
            prompt = task.get_prompt(doc)
            err = prompt_checks(prompt, parts['context'], [d['text'] for d in rag_rows[i]['docs']])
            ids = gen.encode(prompt)
            ctx_tokens = gen.count(parts['context']) if parts['context'] else 0
            row_meta = {'dataset': m['dataset'], 'task_id': task_id, 'subset_key': m['subset_key']}
            if err:
                skipped.append(dict(row_meta, reason=err))
                continue
            if ctx_tokens > m['token_budget']:
                skipped.append(dict(row_meta, reason='measured context tokens exceed budget',
                                    context_tokens_actual=ctx_tokens, token_budget=m['token_budget']))
                continue
            if len(ids) + params['max_new_tokens'] > gen.max_context:
                skipped.append(dict(row_meta, reason='prompt + max_new_tokens exceeds model context',
                                    input_tokens=len(ids), max_context=gen.max_context))
                continue
            roundtrip = gen.decode(ids) == prompt
            for sid in sample_ids:
                key = sample_key(m['dataset'], task_id, m['subset_key'], sid)
                if key not in gens:
                    seed = base_seed + sid
                    rec = dict(row_meta, key=key, sample_id=sid, seed=seed, manifest_row=i,
                               prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), prompt=prompt,
                               input_tokens=len(ids), context_tokens_actual=ctx_tokens,
                               context_tokens_manifest=m['context_tokens'], prompt_decode_roundtrip=roundtrip)
                    try:
                        g = gen.generate(ids, seed, params, stop_words)
                        # Upstream passes decode(prompt+generation) to postprocess with
                        # new_tokens_only=False; we pass the exact prompt string + decoded continuation.
                        program = task.postprocess_generation(prompt + g['new_text'], i, new_tokens_only=False)
                        rec.update(g, program=program, error=None)
                    except Exception as e:  # recorded, never scored
                        rec.update(error=f'generation: {type(e).__name__}: {e}', program=None)
                    append_jsonl(gens_path, rec)
                    gens[key] = rec
                    log(f"gen {key} tokens={rec.get('generated_tokens')} {rec.get('latency_s', 0):.1f}s "
                        f"{rec.get('stop_reason')}")
                if gens[key]['program'] is not None and key not in evals:
                    pending.append({'key': key, 'candidate': gens[key]['program'], 'reference': task.get_reference(doc)})
        if pending:
            t0 = time.perf_counter()
            try:
                res, elog = evaluate_fn(pending)
            except Exception as e:
                append_jsonl(out / 'raw' / 'eval_logs.jsonl', {'task_id': task_id, 'error': str(e)})
                log(f'evaluation failed for {task_id}: {e}')
                res, elog = {}, None
            if elog is not None:
                append_jsonl(out / 'raw' / 'eval_logs.jsonl', {'task_id': task_id, 'log': elog,
                                                               'wall_s': time.perf_counter() - t0})
            for k, v in res.items():
                row = {'key': k, **v}
                append_jsonl(evals_path, row)
                evals[k] = row

    keys_in_scope = {sample_key(m['dataset'], m['task_id'], m['subset_key'], s) for m in manifest for s in sample_ids}
    for key in sorted(keys_in_scope, key=lambda k: (k.split('|')[:3], int(k.split('|')[3]))):
        g = gens.get(key)
        if g is None:
            continue  # row skipped before generation (listed in skipped.jsonl)
        if g['error'] is not None or key not in evals:
            skipped.append({'dataset': g['dataset'], 'task_id': g['task_id'], 'subset_key': g['subset_key'],
                            'sample_id': g['sample_id'],
                            'reason': g['error'] or 'not evaluated (see raw/eval_logs.jsonl)'})
            continue
        e = evals[key]
        results.append({
            'dataset': g['dataset'], 'task_id': g['task_id'], 'subset_key': g['subset_key'],
            'sample_id': g['sample_id'], 'seed': g['seed'], 'passed': e['passed'],
            'eval_result': e['result'], 'error': None if e['passed'] else e['result'],
            'model_id': model_meta['model_id'], 'model_revision': model_meta['model_revision'],
            'generation_params': params, 'input_tokens': g['input_tokens'],
            'context_tokens_actual': g['context_tokens_actual'], 'context_tokens_manifest': g['context_tokens_manifest'],
            'generated_tokens': g['generated_tokens'], 'latency_s': round(g['latency_s'], 3),
            'stop_reason': g['stop_reason'], 'prompt_sha256': g['prompt_sha256'],
        })
    oa.write_jsonl(out / 'results.jsonl', results)
    oa.write_jsonl(out / 'skipped.jsonl', skipped)
    return results, skipped


def main():
    ap = argparse.ArgumentParser(description='Run manifest subsets with a frozen local model + official evaluator')
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--candidates', required=True)
    ap.add_argument('--odex', required=True, help='neulab/odex en_test.jsonl (pinned)')
    ap.add_argument('--model-dir', required=True)
    ap.add_argument('--model-id', required=True)
    ap.add_argument('--model-revision', required=True)
    ap.add_argument('--upstream', required=True, help='code-rag-bench checkout (pinned SHA)')
    ap.add_argument('--sandbox-python', required=True, help='interpreter outside /root,/home,/tmp')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--samples', type=int, default=5)
    ap.add_argument('--base-seed', type=int, default=0)
    ap.add_argument('--max-new-tokens', type=int, default=256)
    ap.add_argument('--temperature', type=float, default=UPSTREAM_DEFAULTS['temperature'])
    ap.add_argument('--top-p', type=float, default=UPSTREAM_DEFAULTS['top_p'])
    ap.add_argument('--threads', type=int, default=None)
    ap.add_argument('--only-subsets', nargs='*', help='e.g. none (no-retrieval smoke)')
    ap.add_argument('--limit-tasks', type=int)
    ap.add_argument('--eval-timeout', type=float, default=3.0, help='upstream ODEX default 3.0s per program')
    args = ap.parse_args()

    import os
    os.environ['CRAG_UPSTREAM'] = args.upstream
    import crag_upstream
    import sandbox
    import sandbox_eval
    ok, rep = sandbox.self_test(args.sandbox_python)
    if not ok:
        sys.exit(f'sandbox self-test failed, refusing to execute generated code: {rep}')
    sha, dirty = crag_upstream.upstream_sha(), crag_upstream.upstream_dirty()
    if sha != crag_upstream.PINNED_SHA or dirty:
        sys.exit(f'upstream checkout {sha} dirty={dirty}; expected clean {crag_upstream.PINNED_SHA}')

    params = dict(UPSTREAM_DEFAULTS, temperature=args.temperature, top_p=args.top_p,
                  max_new_tokens=args.max_new_tokens)
    gen = HFGenerator(args.model_dir, args.threads)
    weights = sorted(Path(args.model_dir).glob('*.safetensors'))
    model_meta = {'model_id': args.model_id, 'model_revision': args.model_revision,
                  'weights_sha256': {w.name: oa.sha256_file(w) for w in weights}, **gen.info}
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    config = {'argv': sys.argv, 'python': platform.python_version(), 'upstream_sha': sha, 'model': model_meta,
              'generation_params': params, 'sample_ids': list(range(args.samples)),
              'seeds': [args.base_seed + s for s in range(args.samples)],
              'seed_note': 'torch.manual_seed(base_seed+sample_id) before each generate; equal seeds do NOT '
                           'imply equal sampling trajectories across different prompts',
              'odex_sha256': oa.sha256_file(args.odex), 'manifest_sha256': oa.sha256_file(args.manifest),
              'candidates_sha256': oa.sha256_file(args.candidates), 'sandbox_self_test': rep,
              'eval_timeout_s': args.eval_timeout}
    (out / 'run_config.json').write_text(json.dumps(config, indent=2, ensure_ascii=False))

    results, skipped = run(
        oa.read_jsonl(args.manifest), oa.read_jsonl(args.candidates), oa.load_odex(args.odex), gen,
        lambda progs: sandbox_eval.evaluate(progs, args.sandbox_python, args.upstream, args.eval_timeout),
        oa.upstream_odex_task, out, list(range(args.samples)), args.base_seed, params, model_meta,
        args.only_subsets, args.limit_tasks)
    print(f'results={len(results)} passed={sum(r["passed"] for r in results)} skipped={len(skipped)} -> {out}')


if __name__ == '__main__':
    main()
