"""ODEX-en helpers shared by task selection, retrieval, normalization and run_manifest.

Task identity follows upstream retrieval (`retrieval/create/odex.py`): query id is
f"{row_index}_{task_id}" because ODEX task_ids are not unique (66 of 333 repeat in en).
"""
import hashlib
import json
import sys
from pathlib import Path

import crag_upstream

DATASET = 'odex-en'
# Tasks whose tests need network, processes, the host filesystem or wall-clock state cannot
# be judged fairly in a no-network read-only sandbox; excluded by rule, before any generation.
SIDE_EFFECT_LIBS = {'os', 'subprocess', 'socket', 'urllib', 'ftplib', 'shutil', 'sys', 'time', 'filecmp',
                    'sqlite3', 'requests', 'multiprocessing', 'signal', 'tempfile', 'glob', 'pathlib', 'io'}


def read_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def task_key(index, record):
    return f"{index}_{record['task_id']}"


def group_of(record):
    return '+'.join(sorted(record['library'])) or 'builtins'


def load_odex(path):
    """{task_key: record} in file order; each record gets `source_index`."""
    out = {}
    for i, r in enumerate(read_jsonl(path)):
        out[task_key(i, r)] = dict(r, source_index=i)
    return out


def select_tasks(odex, canonical_rows, n, stdlib=None):
    """Deterministic pilot slice: first `n` tasks (file order) whose libraries are all stdlib
    modules without host side effects and that have >=1 upstream canonical (gold) doc.
    Gold docs are used only as a 'documentation is relevant' filter, never as candidates."""
    stdlib = stdlib or set(sys.stdlib_module_names)
    picked, reasons = [], {}
    for key, rec in odex.items():
        canon = canonical_rows[rec['source_index']]
        if canon['intent'] != rec['intent'] or str(canon['task_id']) != str(rec['task_id']):
            raise ValueError(f'canonical file misaligned at {key}')
        libs = set(rec['library'])
        if not libs <= stdlib:
            reasons[key] = 'non-stdlib library'
        elif libs & SIDE_EFFECT_LIBS:
            reasons[key] = 'side-effect library'
        elif not canon['docs']:
            reasons[key] = 'no canonical doc'
        elif len(picked) < n:
            picked.append(key)
    return picked, reasons


def upstream_odex_task(rag_inputs_path, topk_docs):
    """Instantiate the official GeneralODEX exactly as `main.py --dataset_path json
    --data_files_test <file>` would (lang 'en')."""
    odex_mod = crag_upstream.load('eval.tasks.odex')
    return odex_mod.create_task('en')(dataset_path='json', data_files={'test': str(rag_inputs_path)},
                                      topk_docs=topk_docs)
