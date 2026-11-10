import copy
import importlib.util
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vocabulary_pilot', ROOT / 'scripts/pilot-passage-extraction.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RelationVocabularyTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / 'schemas/extraction.schema.json').read_text(encoding='utf-8'))
        self.sample = json.loads((ROOT / 'data/extraction/sample.json').read_text(encoding='utf-8'))

    def test_generator_and_both_contracts_use_same_allowlist(self):
        other = json.loads((ROOT / 'schemas/extraction-candidates.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(set(m.TYPES), set(self.schema['$defs']['relation']['properties']['type']['enum']))
        self.assertEqual(set(m.TYPES), set(other['$defs']['relation']['properties']['type']['enum']))

    def test_sql_relation_requires_updated_version(self):
        data = copy.deepcopy(self.sample)
        data['relations'][0]['type'] = 'FILTERS'
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.schema).validate(data)
        data['schema_version'] = '0.1.2'
        Draft202012Validator(self.schema).validate(data)

    def test_initial_sample_remains_valid(self):
        Draft202012Validator(self.schema).validate(self.sample)


if __name__ == '__main__':
    unittest.main()
