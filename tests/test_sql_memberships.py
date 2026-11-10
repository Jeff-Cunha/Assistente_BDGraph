import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sql_membership', ROOT / 'scripts/extract-aggregate-memberships.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MembershipTests(unittest.TestCase):
    def test_reads_the_source_list_instead_of_inventing_functions(self):
        text = 'PostgreSQL supports aggregate functions. An aggregate function computes a result; `count`, `sum`, `avg`, `max`, `min`.'
        self.assertEqual(m.listed_functions(text), ['count','sum','avg','max','min'])

    def test_unrelated_code_not_treated_as_definition(self):
        with self.assertRaises(ValueError):
            m.listed_functions('SELECT count(*) FROM weather;')


if __name__ == '__main__':
    unittest.main()
