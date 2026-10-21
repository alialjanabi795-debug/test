#!/usr/bin/env python3
"""Analyze real per-subset pass/fail outcomes. Never executes model-generated code.

This reports exploratory empirical patterns, not statistical proof of complementarity.
"""
import argparse
import collections
import json
import math
import random
import statistics
from pathlib import Path


def rows(path):
    with open(path, encoding='utf-8') as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f'{path}:{n}: {e}') from e


def med(xs):
    return statistics.median(xs) if xs else None


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def label(c):
    return 'none' if not c else '+'.join(f'r{i+1}' for i in c)


def subset_indices(k):
    if k == 'none':
        return ()
    return tuple(sorted(int(p[1:])-1 for p in k.split('+')))


def empirical_greedy(ps, tokens, budget, max_docs=2):
    """Oracle-informed greedy DIAGNOSTIC: scores come from observed tests; not deployable or PACE."""
    indices = sorted({idx for key in ps for idx in subset_indices(key)})
    selected = ()
    while len(selected) < max_docs:
        cand = []
        for i in indices:
            if i in selected:
                continue
            prospective = tuple(sorted(selected+(i,)))
            k = label(prospective)
            if k in ps and tokens.get(k, math.inf) <= budget:
                cand.append((ps[k]-ps[label(selected)], -i, prospective))
        if not cand:
            break
        # Tie-break by original document rank; can include zero-gain docs within budget.
        _, _, selected = max(cand)
    return label(selected)


def summarize_task(meta, result, min_samples, eps=0.2):
    allkeys = set(meta)
    available = {s: v for s, v in result.items() if len(v) >= min_samples}
    if not allkeys.issubset(available):
        return None
    p = {s: mean([int(x['passed']) for x in available[s]]) for s in allkeys}
    topset = next(iter(meta.values()))['topk_subset_key']
    budget = next(iter(meta.values()))['token_budget']
    tok = {s: row['context_tokens'] for s, row in meta.items()}
    if topset not in p or 'none' not in p:
        raise ValueError('Missing baseline subset')
    oracle = sorted(p, key=lambda s: (-p[s], tok[s], len(subset_indices(s)), s))[0]
    greedy = empirical_greedy(p, tok, budget, max_docs=next(iter(meta.values()))['max_docs'])
    base = p['none']
    interaction = []
    compl_pairs = []
    for s in p:
        c = subset_indices(s)
        if len(c) != 2:
            continue
        x,y = c
        ka,kb = label((x,)),label((y,))
        if ka not in p or kb not in p:
            continue
        val = p[s]-p[ka]-p[kb]+base
        interaction.append((s, round(val, 8)))
        if base <= eps and p[ka] <= eps and p[kb] <= eps and p[s] >= 1-eps:
            compl_pairs.append(s)
    us = list(p.values())
    return {
        'task_id': next(iter(meta.values()))['task_id'],
        'dataset': next(iter(meta.values()))['dataset'],
        'group': next(iter(meta.values()))['group'],
        'swing_raw': int(max(us) > min(us)),
        'swing_spread': max(us)-min(us),
        'swing_strong_exploratory': int(max(us)-min(us) >= 0.4-1e-9),
        'topk_utility': p[topset], 'topk_subset': topset,
        'oracle_utility': p[oracle], 'oracle_subset': oracle,
        'oracle_headroom': p[oracle]-p[topset],
        'greedy_utility': p[greedy], 'greedy_subset': greedy,
        'greedy_regret': p[oracle]-p[greedy],
        'interaction_max': max([v for _,v in interaction], default=None),
        'positive_interaction_pairs': sum(v > eps for _,v in interaction),
        'tested_pairs': len(interaction),
        'has_positive_interaction': int(any(v > eps for _,v in interaction)),
        'complementary_pairs_exploratory': compl_pairs,
        'has_complementary_pair': int(bool(compl_pairs)),
        'sample_count_min': min(map(len, available.values())),
        'sample_count_max': max(map(len, available.values())),
        'subsets_tested': len(p),
    }


def interval_by_task(items, field, trials=1000):
    vals = [float(x[field]) for x in items]
    if not vals:
        return None
    rng = random.Random(20261021)
    n = len(vals)
    bs = [sum(rng.choice(vals) for _ in range(n))/n for _ in range(trials)]
    bs.sort()
    return [round(bs[int(.025*(trials-1))], 4), round(bs[int(.975*(trials-1))], 4)]


def summarize(group):
    if not group:
        return None
    metrics = ['swing_raw','swing_strong_exploratory','has_positive_interaction',
               'has_complementary_pair','oracle_headroom','greedy_regret',
               'topk_utility','oracle_utility','greedy_utility']
    return {'num_tasks': len(group), 'metrics': {
        k: {'mean':round(mean([x[k] for x in group]),4), '95pct_task_bootstrap':interval_by_task(group,k)}
        for k in metrics}}


def main():
    ap = argparse.ArgumentParser(description='Analyze CodeRAG evidence complementarity pilot')
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--results', required=True)
    ap.add_argument('--out', required=True, help='Output directory')
    ap.add_argument('--min-samples', type=int, default=5)
    ap.add_argument('--allow-synthetic', action='store_true', help='Required only for demo examples')
    args = ap.parse_args()
    if args.min_samples < 1:
        ap.error('min-samples must be positive')
    meta = collections.defaultdict(dict)
    for row in rows(args.manifest):
        key = (row['dataset'],row['task_id'])
        s = row['subset_key']
        if s in meta[key]:
            raise ValueError(f'Duplicate manifest subset {key} {s}')
        meta[key][s] = row
    results = collections.defaultdict(lambda: collections.defaultdict(list))
    count = 0
    signatures = set()
    for row in rows(args.results):
        if row.get('synthetic') and not args.allow_synthetic:
            raise ValueError('Synthetic example data rejected. Add --allow-synthetic for demo only.')
        key = (row['dataset'], row['task_id'])
        sub = row['subset_key']
        if key not in meta or sub not in meta[key]:
            raise ValueError(f'Result without matching manifest: {key} / {sub}')
        if type(row.get('passed')) is not bool:
            raise ValueError('passed must be true/false (bool)')
        sig = (key,sub,str(row['sample_id']))
        if sig in signatures:
            raise ValueError(f'Duplicate result: {sig}')
        signatures.add(sig)
        results[key][sub].append(row)
        count += 1
    all_task_results = []
    incomplete = []
    for key, m in meta.items():
        outcome = summarize_task(m, results[key], args.min_samples)
        if outcome:
            all_task_results.append(outcome)
        else:
            missing = [s for s in m if len(results[key][s]) < args.min_samples]
            incomplete.append({'dataset':key[0], 'task_id':key[1], 'missing_or_under_sampled': missing})
    bydataset = collections.defaultdict(list)
    for r in all_task_results:
        bydataset[r['dataset']].append(r)
    report = {
        'IMPORTANT': 'Real benchmarks must be run externally. This script analyzes supplied pass/fail records only. Oracle and observed-utility greedy are retrospective and are not deployable.',
        'num_results':count, 'num_manifest_tasks':len(meta),
        'num_analyzed_tasks':len(all_task_results), 'num_incomplete_tasks':len(incomplete),
        'exploratory_thresholds': {'positive_interaction': 0.2, 'complementary_single_max':0.2, 'complementary_pair_min':0.8, 'swing_strong_spread':0.4},
        'overall': summarize(all_task_results),
        'per_dataset': {k:summarize(v) for k,v in sorted(bydataset.items())},
        'tasks': all_task_results, 'incomplete':incomplete,
    }
    path = Path(args.out)
    path.mkdir(parents=True, exist_ok=True)
    (path/'analysis.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ["# تقرير تحليل الأدلة — تجريبي فقط", "", f"عدد سجلات التنفيذ: {count}",
             f"المسائل المكتملة: {len(all_task_results)} / {len(meta)}", "",
             "**تنبيه:** Oracle وEmpirical Greedy يعتمدان على نتائج الاختبارات المعروفة بعد التنفيذ، ولا يجوز اعتبارهما خوارزميات قابلة للاستخدام المباشر.",
             "الفواصل أدناه Bootstrap على مستوى المسألة فقط ولا تشمل كل عدم اليقين الناجم عن تكرارات التوليد أو اختيار أفضل subset.",
             "عتبات التكامل الموجب/الزوج المكمل (0.2 و0.8) استكشافية وليست اختبار دلالة إحصائية.", ""]
    for dataset, summary in [('الكل',summarize(all_task_results))]+[(k,summarize(v)) for k,v in sorted(bydataset.items())]:
        lines.append(f"## {dataset}")
        if not summary:
            lines.append('لا توجد مسائل مكتملة')
            continue
        lines.append(f"عدد المسائل: {summary['num_tasks']}")
        mapping = {'swing_raw':'Swing خام','swing_strong_exploratory':'Swing بفارق ≥ 0.4','has_positive_interaction':'مسائل بها تفاعل موجب','has_complementary_pair':'مسائل بها زوج تكاملي قوي', 'oracle_headroom':'فرصة تحسين Oracle فوق Top-k','greedy_regret':'فجوة Empirical Greedy إلى Oracle', 'topk_utility':'Top-k Pass','oracle_utility':'Oracle Pass','greedy_utility':'Empirical Greedy Pass'}
        for k, item in summary['metrics'].items():
            lo,hi = item['95pct_task_bootstrap']
            lines.append(f"- {mapping[k]}: **{item['mean']:.3f}** (bootstrap: {lo:.3f}–{hi:.3f})")
        lines.append('')
    if incomplete:
        lines.append('## سجلات غير مكتملة')
        lines.append(f'يوجد {len(incomplete)} مسألة لم تُستكمل جميع الحالات لها، ولم تدخل في المتوسطات.')
    (path/'REPORT_AR.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(f'Analyzed {len(all_task_results)} complete tasks; incomplete={len(incomplete)}; output={path}')

if __name__ == '__main__':
    main()
