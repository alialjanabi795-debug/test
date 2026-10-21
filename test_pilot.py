#!/usr/bin/env python3
import unittest
from prepare_manifest import generate
from analyze_pilot import summarize_task

class PilotTest(unittest.TestCase):
    def setUp(self):
        task={'task_id':'x','dataset':'d','group':'g','docs':[
            {'id':f'd{i}','rank':i,'tokens':10} for i in range(1,6)]}
        self.meta={r['subset_key']:r for r in generate([task],budget=100)}
    def test_manifest_cardinality(self):
        self.assertEqual(len(self.meta), 16)
        self.assertEqual(self.meta['r1+r2']['doc_ids'],['d1','d2'])
    def test_complementarity(self):
        results={k:[{'passed':k=='r3+r4'} for _ in range(5)] for k in self.meta}
        s=summarize_task(self.meta,results,5)
        self.assertEqual(s['has_complementary_pair'],1)
        self.assertEqual(s['greedy_regret'],1)
        self.assertEqual(s['oracle_headroom'],1)
    def test_budget_blocks_pair(self):
        task={'task_id':'x','dataset':'d','group':'g','docs':[
            {'id':'a','rank':1,'tokens':70},{'id':'b','rank':2,'tokens':70}]}
        subsets=list(generate([task], budget=100))
        self.assertEqual(len(subsets),3)

if __name__=='__main__': unittest.main()
