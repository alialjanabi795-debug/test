# مهمة Codex التنفيذية — اربط الأداة بالـBenchmark فقط

You are the implementation engineer for a PhD feasibility pilot on CodeRAG-Bench. Work inside my local workspace.

**DO NOT conduct a literature review, invent citations, train a model, or propose a new algorithm.** First inspect the files shipped with this pilot: `README_AR.md`, `prepare_manifest.py`, `analyze_pilot.py`, and `test_pilot.py`.

Goal: produce **real** execution-evaluated pass/fail results for evidence subsets, using the official CodeRAG-Bench codebase: https://github.com/code-rag-bench/code-rag-bench.

## Phase A: inspect and verify without downloads
1. Inspect CPU, RAM, GPU (if any), disk space, OS, Python, installed packages, local LLM, available models, and `git`.
2. Check whether CodeRAG-Bench and its benchmark datasets are already available locally; report git commit SHA. Propose (but do not automatically perform) downloads or dependency changes, stating size and justification.
3. Investigate the real retrieval JSON schema and the real generation/evaluation adapter in `generation/main.py`. Keep upstream unmodified where practical; write an adapter or an isolated patch with a diff.
4. Confirm that the official execution evaluator can run in a sandboxed/limited container. Never execute model-generated code with unrestricted network/filesystem access. If no reliable sandbox is available, STOP before evaluation and report the blocker.

## Phase B: 5–10 real-task smoke test AFTER all required resources are approved
5. Select 5–10 DS-1000/ODEX development tasks with official executable test support. Never mix task data from test split into training.
6. Retrieve exactly five candidate documents per task (or fewer if the index lacks five), using one frozen retriever/index and save original text, ID, rank, score, token count, and index fingerprint.
7. Normalize input to `candidates.jsonl` as specified in the pilot README, then run `prepare_manifest.py --topn 5 --max-docs 2 --budget 4096`.
8. Implement `run_manifest.py`: for each manifest row and seed, construct an identical canonical task prompt with only the selected documents changed; preserve rank order; include a no-retrieval mode; check the **actual tokenizer count** for full context and truncate nothing silently. Record every skipped case and reason.
9. Use one frozen local generator model and the official CodeRAG-Bench execution-based evaluator. Produce `results.jsonl` containing dataset, task_id, subset_key, sample_id, passed (boolean from real tests), model_id, generation parameters, total input tokens, generated tokens, latency, and error details; preserve raw outputs/logs separately.
10. Use identical sample IDs across all subsets. Do not claim that random seeds cause identical sampling trajectories. If reproducibility differs across modes, say so.
11. Run `python analyze_pilot.py --manifest manifest.jsonl --results results.jsonl --out real_report --min-samples 5` only when data coverage permits. Distinguish incomplete cases.

## Constraints
- Do NOT download large LLMs or install heavy packages without explicit user permission.
- Do NOT invent pass rates, runtimes, power figures, or benchmark results.
- Do NOT label the retrospective empirical greedy diagnostic as PACE. PACE reproduction would be separate work.
- Do NOT claim the identified pattern is novel without a literature audit.
- Do NOT introduce RL, training, learned rerankers, or new scientific claims.
- Pin exact code and dataset versions and document any missing compatibility/reproduction issue.
- Prioritize a minimal working smoke test instead of running hundreds of tasks.

## Deliverables
- `run_manifest.py` and any normalization adapter (with tests).
- `candidates.jsonl`, `manifest.jsonl`, `results.jsonl` produced from **real** inputs, if technically feasible.
- `real_report/REPORT_AR.md` and `real_report/analysis.json`, if all requirements satisfied.
- `PHASE_A_B_REPORT_AR.md`: hardware; environment; actual commands; dataset versions; code changes; successful/failing tasks; permissions requested; missing steps; and an explicit READY / BLOCKED verdict.

Start Phase A immediately and request approval only for steps that require downloads, installation, or unsafe execution.
