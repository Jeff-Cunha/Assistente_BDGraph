import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('glossary', ROOT / 'scripts/extract-glossary-concepts.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def chunk(cid, text):
    return dict(document_id='D01', chunk_id=cid, text=text, source_url='https://example.org/source')


class GlossaryTests(unittest.TestCase):
    def test_carries_section_across_chunks_and_stops_at_exercises(self):
        a = chunk('D01_C001', '## Key Terms\n\n<strong>key</strong>: a source definition')
        b = chunk('D01_C002', '<strong>table</strong>: another definition\n\n## Exercises\n\n<strong>not a term</strong>: a question')
        self.assertEqual([x['surface'] for x in m.extract([a, b])], ['key', 'table'])

    def test_colon_inside_markup_and_exact_offsets(self):
        a = chunk('D01_C001', '## Key Terms and Abbrevations\n\n<strong>first normal form (1NF):</strong> the original explanation')
        e = m.extract([a])[0]
        self.assertEqual(e['surface'], 'first normal form (1NF)')
        self.assertEqual(a['text'][e['start']:e['end']], e['quote'])

    def test_does_not_treat_unrelated_bold_text_as_glossary(self):
        self.assertEqual(m.extract([chunk('D01_C001', '<strong>Note</strong>: explanation')]), [])

    def test_acronym_alias_maps_to_known_id_without_changing_quote(self):
        a = chunk('D01_C001', '## Key Terms\n\n<strong>foreign key (FK)</strong>: explanation')
        known = [dict(concept_id='C_foreign_key', canonical_name='foreign key', name_pt='chave estrangeira', aliases=['FK'])]
        e = m.extract([a], known)[0]
        self.assertEqual(e['existing_concept_id'], 'C_foreign_key')
        self.assertIn('(FK)', e['quote'])

    def test_adjacent_definitions_are_split_without_rewriting_source(self):
        a = chunk('D01_C001', '## Key Terms\n\n<strong>alternate key</strong>: first definition<strong>candidate key</strong>: second definition')
        result = m.extract([a])
        self.assertEqual([e['surface'] for e in result], ['alternate key', 'candidate key'])
        self.assertEqual(result[0]['definition_source_text'], 'first definition')
        for e in result:
            self.assertEqual(a['text'][e['start']:e['end']], e['quote'])


if __name__ == '__main__':
    unittest.main()
