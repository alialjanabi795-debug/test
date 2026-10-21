#!/usr/bin/env python3
"""Generate clearly fake records solely to check the pipeline."""
import json
from pathlib import Path
from prepare_manifest import generate

out = Path(__file__).parent/'examples'
out.mkdir(exist_ok=True)
# Not CodeRAG-Bench questions. Intentionally constructed to exercise different outcomes.
tasks = [
    {'task_id':'DEMO_synergy','dataset':'SYNTHETIC','group':'demo','docs':[{'id':f'd{i}','rank':i,'tokens':180} for i in range(1,6)]},
    {'task_id':'DEMO_constant','dataset':'SYNTHETIC','group':'demo','docs':[{'id':f'd{i}','rank':i,'tokens':180} for i in range(1,6)]},
    {'task_id':'DEMO_retrieval_error','dataset':'SYNTHETIC','group':'demo','docs':[{'id':f'd{i}','rank':i,'tokens':180} for i in range(1,6)]},
]
with (out/'sample_candidates_SYNTHETIC.jsonl').open('w',encoding='utf-8') as f:
    for t in tasks:
        f.write(json.dumps(t)+'\n')
manifest = list(generate(tasks))
with (out/'sample_manifest_SYNTHETIC.jsonl').open('w',encoding='utf-8') as f:
    for m in manifest:
        f.write(json.dumps(m)+'\n')
with (out/'sample_results_SYNTHETIC.jsonl').open('w',encoding='utf-8') as f:
    for m in manifest:
        for seed in range(5):
            key = m['subset_key']
            if m['task_id']=='DEMO_synergy':
                passed = key=='r3+r4'
            elif m['task_id']=='DEMO_constant':
                passed = True
            else:
                passed = 'r5' in key
            f.write(json.dumps({'dataset':'SYNTHETIC','task_id':m['task_id'],
                                'subset_key':key,'sample_id':seed,'passed':passed,
                                'synthetic':True, 'latency_s':0.0})+'\n')
print('Wrote SYNTHETIC-only demonstration files under examples/')
