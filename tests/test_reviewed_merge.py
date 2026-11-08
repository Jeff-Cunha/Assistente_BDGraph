import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reviewed_merge', ROOT / 'scripts/merge-reviewed-extractions.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ReviewedMergeTests(unittest.TestCase):
    def graph(self):
        return dict(extraction_method='llm_candidates', input_chunk_ids=['T1'],
            concepts=[dict(concept_id='C_a', canonical_name='a', category='general', aliases=[],
                           evidence=[dict(chunk_id='T1', quote='a')], review_status='accepted')],
            relations=[])

    def test_same_concept_and_evidence_not_duplicated(self):
        g = self.graph()
        out = m.merge([g, copy.deepcopy(g)])
        self.assertEqual(len(out['concepts']), 1)
        self.assertEqual(len(out['concepts'][0]['evidence']), 1)

    def test_manual_and_model_outputs_not_silently_mixed(self):
        g, h = self.graph(), self.graph()
        h['extraction_method'] = 'manual_reference'
        with self.assertRaises(ValueError):
            m.merge([g, h])

    def test_pending_concept_not_promoted(self):
        g = self.graph()
        g['concepts'][0]['review_status'] = 'pending'
        with self.assertRaises(ValueError):
            m.merge([g])

    def test_conflicting_canonical_id_rejected(self):
        g, h = self.graph(), self.graph()
        h['concepts'][0]['concept_id'] = 'C_other'
        with self.assertRaises(ValueError):
            m.merge([g, h])


if __name__ == '__main__':
    unittest.main()
