#!/usr/bin/env python3
"""Offline tests for the CodeRAG-Bench adapters. No model, no downloads.

Upstream-backed and sandbox tests run only when CRAG_UPSTREAM is set / tools are present.
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

import normalize_candidates
import odex_adapter as oa
import prepare_manifest
import retrieve_bm25
import run_manifest


def odex_rec(tid, intent, libs=()):
    return {'task_id': tid, 'prompt': f'def f_{tid}():\n\treturn ', 'suffix': '', 'canonical_solution': '1',
            'test_start': '\ndef check(candidate):', 'test': ['\n    assert candidate() == 1\n'],
            'entry_point': f'f_{tid}', 'intent': intent, 'library': list(libs)}


class FakeTask:
    """Mimics the GeneralODEX surface run_manifest uses (prompt format copied from upstream)."""
    stop_words = ['\ndef']

    def __init__(self, path, topk):
        self.rows, self.topk = oa.read_jsonl(path), topk

    def get_dataset(self):
        return self.rows

    def get_prompt(self, doc, return_dict=False):
        ctx = ''
        if doc['docs']:
            ctx = 'Please refer to the following documentation to generate the code:\n' + '\n'.join(
                d['text'] for d in doc['docs'][:self.topk])
        p = doc['prompt'].replace('\t', '    ')
        return {'prompt': p, 'context': ctx} if return_dict else ctx + '\n' + p

    def postprocess_generation(self, gen, idx, new_tokens_only=False):
        d = self.get_prompt(self.rows[idx], return_dict=True)
        return d['prompt'] + gen[len(d['context'] + '\n' + d['prompt']):].split('\ndef')[0]

    def get_reference(self, doc):
        return doc['test_start'] + ''.join(doc['test']) + f"\ncheck({doc['entry_point']})"


class FakeGen:
    max_context = 10_000
    eos_token = '<eos>'

    def __init__(self, answer='1'):
        self.answer, self.calls = answer, []

    def encode(self, text):
        return list(range(len(text.split())))

    def count(self, text):
        return len(text.split())

    def decode(self, ids):
        return None

    def generate(self, ids, seed, params, stop_words):
        self.calls.append(seed)
        return {'new_text': self.answer + '\ndef junk', 'generated_tokens': 3, 'latency_s': 0.01, 'stop_reason': 'stop_word'}


def fake_eval(progs):
    return {p['key']: {'passed': p['candidate'].rstrip().endswith('return 1'), 'result': 'fake'} for p in progs}, {}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.odex = {'0_7': dict(odex_rec(7, 'add one'), source_index=0)}
        docs = [{'id': str(i), 'title': f't{i}', 'text': f'doc {i} ' + 'w ' * i, 'rank': i, 'score': 10.0 - i}
                for i in range(1, 6)]
        retrieval = [{'task_id': '0_7', 'dataset': 'odex-en', 'group': 'builtins', 'docs': docs[::-1],
                      'index_fingerprint': 'fp'}]
        self.cands = normalize_candidates.normalize(retrieval, lambda t: len(t.split()), 'fake')
        self.manifest = list(prepare_manifest.generate(self.cands, topn=5, max_docs=2, budget=4096))

    def tearDown(self):
        self.tmp.cleanup()

    def test_normalize_schema_and_rank_order(self):
        c = self.cands[0]
        self.assertEqual([d['rank'] for d in c['docs']], [1, 2, 3, 4, 5])
        self.assertEqual(c['docs'][0]['tokens'], 3)  # 'doc 1 w'
        for k in ('id', 'rank', 'tokens', 'score', 'text', 'title'):
            self.assertIn(k, c['docs'][0])
        self.assertEqual(len(self.manifest), 16)

    def test_normalize_rejects_gapped_ranks(self):
        bad = [{'task_id': 'x', 'dataset': 'd', 'group': 'g', 'index_fingerprint': 'f',
                'docs': [{'id': 'a', 'rank': 1, 'score': 1, 'title': '', 'text': 'a'},
                         {'id': 'b', 'rank': 3, 'score': 1, 'title': '', 'text': 'b'}]}]
        with self.assertRaises(ValueError):
            normalize_candidates.normalize(bad, len, 'x')

    def test_rag_inputs_only_docs_change(self):
        rows = run_manifest.build_rag_inputs(self.manifest, self.cands, self.odex)
        by = {r['crag_subset_key']: r for r in rows}
        self.assertEqual(by['none']['docs'], [])
        self.assertEqual([d['text'] for d in by['r2+r4']['docs']], [self.cands[0]['docs'][1]['text'],
                                                                     self.cands[0]['docs'][3]['text']])
        strip = lambda r: {k: v for k, v in r.items() if not k.startswith('crag_') and k != 'docs'}
        self.assertTrue(all(strip(r) == strip(rows[0]) for r in rows))

    def test_run_identical_sample_ids_and_resume(self):
        gen = FakeGen()
        meta = {'model_id': 'fake', 'model_revision': 'r'}
        params = dict(run_manifest.UPSTREAM_DEFAULTS, max_new_tokens=8)
        res, sk = run_manifest.run(self.manifest, self.cands, self.odex, gen, fake_eval, FakeTask, self.d,
                                   [0, 1, 2], 100, params, meta, log=lambda *_: None)
        self.assertEqual(len(res), 16 * 3)
        self.assertEqual(sk, [])
        ids = {}
        for r in res:
            ids.setdefault(r['subset_key'], set()).add(r['sample_id'])
            self.assertIs(r['passed'], True)
        self.assertTrue(all(v == {0, 1, 2} for v in ids.values()))
        self.assertEqual(sorted(set(gen.calls)), [100, 101, 102])
        n = len(gen.calls)
        run_manifest.run(self.manifest, self.cands, self.odex, gen, fake_eval, FakeTask, self.d, [0, 1, 2], 100,
                         params, meta, log=lambda *_: None)
        self.assertEqual(len(gen.calls), n, 'resume must not regenerate')
        none_rows = [r for r in res if r['subset_key'] == 'none']
        self.assertTrue(all(r['context_tokens_actual'] == 0 for r in none_rows))

    def test_over_budget_is_skipped_not_truncated(self):
        m = [dict(r, token_budget=5) for r in self.manifest]
        res, sk = run_manifest.run(m, self.cands, self.odex, FakeGen(), fake_eval, FakeTask, self.d, [0], 0,
                                   dict(run_manifest.UPSTREAM_DEFAULTS, max_new_tokens=8),
                                   {'model_id': 'f', 'model_revision': 'r'}, log=lambda *_: None)
        self.assertTrue(sk and all(s['reason'] == 'measured context tokens exceed budget' for s in sk))
        self.assertEqual({r['subset_key'] for r in res}, {'none'})

    def test_generation_error_recorded_not_scored(self):
        class Boom(FakeGen):
            def generate(self, *a):
                raise RuntimeError('oom')
        res, sk = run_manifest.run(self.manifest[:1], self.cands, self.odex, Boom(), fake_eval, FakeTask, self.d,
                                   [0], 0, dict(run_manifest.UPSTREAM_DEFAULTS, max_new_tokens=8),
                                   {'model_id': 'f', 'model_revision': 'r'}, log=lambda *_: None)
        self.assertEqual(res, [])
        self.assertIn('oom', sk[0]['reason'])

    def test_prompt_checks(self):
        self.assertIsNone(run_manifest.prompt_checks('I\na\nb\nX', 'I\na\nb', ['a', 'b']))
        self.assertIsNotNone(run_manifest.prompt_checks('I\nb\na\nX', 'I\nb\na', ['a', 'b']))

    def test_select_tasks_rule(self):
        odex = {f'{i}_{i}': dict(odex_rec(i, f'q{i}', libs), source_index=i)
                for i, libs in enumerate([(), ('os',), ('numpy',), ('re',), ('re',)])}
        canon = [{'task_id': i, 'intent': f'q{i}', 'docs': [] if i == 3 else [{'text': 'x'}]} for i in range(5)]
        picked, why = oa.select_tasks(odex, canon, 5)
        self.assertEqual(picked, ['0_0', '4_4'])
        self.assertEqual(why['1_1'], 'side-effect library')
        self.assertEqual(why['2_2'], 'non-stdlib library')
        self.assertEqual(why['3_3'], 'no canonical doc')

    @unittest.skipUnless(importlib.util.find_spec('rank_bm25'), 'rank_bm25 not installed')
    def test_bm25_ties_by_corpus_order(self):
        import rank_bm25
        docs = [{'id': str(i), 'title': '', 'text': t} for i, t in enumerate(['a b', 'c d', 'a b', 'e f', 'g h', 'i j'])]
        bm = rank_bm25.BM25Okapi([d['text'].split(' ') for d in docs])
        top = retrieve_bm25.retrieve(bm, docs, 'a', 3)
        self.assertEqual([d['id'] for d in top[:2]], ['0', '2'])
        self.assertEqual([d['rank'] for d in top], [1, 2, 3])


@unittest.skipUnless(os.geteuid() == 0 and all(map(__import__('shutil').which, ['unshare', 'setpriv', 'prlimit'])),
                     'sandbox tools/root unavailable')
class SandboxTests(unittest.TestCase):
    def test_self_test(self):
        import sandbox
        ok, rep = sandbox.self_test()
        self.assertTrue(ok, rep)

    @unittest.skipUnless(os.environ.get('CRAG_UPSTREAM'), 'CRAG_UPSTREAM not set')
    def test_official_evaluator_in_sandbox(self):
        import sandbox_eval
        ref = '\ndef check(candidate):\n    assert candidate() == 1\n\ncheck(f)'
        res, _ = sandbox_eval.evaluate(
            [{'key': 'ok', 'candidate': 'def f():\n    return 1', 'reference': ref},
             {'key': 'bad', 'candidate': 'def f():\n    return 2', 'reference': ref},
             {'key': 'net', 'candidate': "import socket\nsocket.create_connection(('1.1.1.1', 443), 2)\n"
                                         'def f():\n    return 1', 'reference': ref}],
            '/usr/bin/python3', os.environ['CRAG_UPSTREAM'])
        self.assertEqual({k: v['passed'] for k, v in res.items()}, {'ok': True, 'bad': False, 'net': False})


@unittest.skipUnless(os.environ.get('CRAG_UPSTREAM') and importlib.util.find_spec('datasets')
                     and importlib.util.find_spec('torch'), 'needs CRAG_UPSTREAM + datasets + torch')
class UpstreamTaskTests(unittest.TestCase):
    def test_upstream_prompt_matches_fake_and_keeps_rank_order(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [dict(odex_rec(1, 'add'), docs=[]),
                    dict(odex_rec(1, 'add'), docs=[{'title': 'a', 'text': 'DOC_A'}, {'title': 'b', 'text': 'DOC_B'}])]
            p = Path(d, 'x.jsonl')
            oa.write_jsonl(p, rows)
            task = oa.upstream_odex_task(p, topk_docs=5)
            ds = task.get_dataset()
            p0, p1 = task.get_prompt(ds[0]), task.get_prompt(ds[1])
            self.assertTrue(p1.endswith(p0))
            self.assertLess(p1.index('DOC_A'), p1.index('DOC_B'))
            prog = task.postprocess_generation(p1 + '1\ndef junk', 1, new_tokens_only=False)
            self.assertNotIn('DOC_A', prog)
            self.assertIn('return 1', prog.replace('\n', ' ').replace('  ', ' '))


if __name__ == '__main__':
    unittest.main()
