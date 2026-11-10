"""Cross-references must stay within their source and must not authorize node merges."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('contextual_alias', ROOT / 'scripts/resolve-contextual-alias.py')
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class ContextualAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry, cls.chunks = resolver.load_registry(ROOT)

    def test_all_three_pending_terms_require_a_document(self):
        for term in ('ER schema', 'single-valued attributes', 'file'):
            result = resolver.resolve(term, self.registry, self.chunks)
            self.assertEqual(result['status'], 'requires_document_context')
            self.assertEqual(result['reference_concept_ids'], [])

    def test_right_document_returns_reference_and_never_merge_permission(self):
        for term, document, target in [('ER schema', 'D02', 'C_entity_relationship_data_model'),
                                       ('single-valued attributes', 'D02', 'C_simple_attribute'),
                                       ('file', 'D09', 'C_relation')]:
            result = resolver.resolve(term, self.registry, self.chunks, document)
            self.assertEqual(result['status'], 'contextual_reference')
            self.assertEqual(result['reference_concept_ids'], [target])
            self.assertFalse(result['auto_merge_nodes'])

    def test_wrong_document_and_substrings_do_not_match(self):
        for term, document in [('file', 'D02'), ('physical file', 'D09'), ('schema', 'D02')]:
            result = resolver.resolve(term, self.registry, self.chunks, document)
            self.assertEqual(result['status'], 'no_match')
            self.assertEqual(result['reference_concept_ids'], [])

    def test_chunk_selects_document_but_mismatched_context_is_rejected(self):
        result = resolver.resolve('file', self.registry, self.chunks, chunk_id='D09_C003')
        self.assertEqual(result['reference_concept_ids'], ['C_relation'])
        with self.assertRaisesRegex(ValueError, 'different sources'):
            resolver.resolve('file', self.registry, self.chunks, 'D02', 'D09_C003')

    def test_fd_exception_requires_chunk_and_does_not_resolve_to_functional_dependency(self):
        result = resolver.resolve('FD', self.registry, self.chunks, 'D05')
        self.assertEqual(result['status'], 'requires_chunk_context')
        result = resolver.resolve('FD', self.registry, self.chunks, chunk_id='D05_C002')
        self.assertEqual(result['status'], 'requires_review')
        self.assertEqual(result['reference_concept_ids'], [])

    def test_modified_source_hash_is_rejected(self):
        # Verify a stale registry fails before reading/using a changed source.
        import json
        root = ROOT / 'work/contextual-hash-rejection'
        root.mkdir(parents=True, exist_ok=True)
        path = root / 'data/normalization/contextual-aliases-v1.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        changed = dict(self.registry)
        changed['protected_files'] = [dict(path='changed.txt', sha256='0' * 64)]
        path.write_text(json.dumps(changed), encoding='utf-8')
        (root / 'changed.txt').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            resolver.load_registry(root)


if __name__ == '__main__':
    unittest.main()
