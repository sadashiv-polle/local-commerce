import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


class SharedCompanySchemaTests(TestCase):
    def test_only_single_company_unique_index_is_removed(self):
        def index(name, column, unique=True):
            return SimpleNamespace(Key_name=name, Column_name=column, Non_unique=0 if unique else 1)
        rows = [index('company', 'company'), index('PRIMARY','name'),
                index('price_list','selling_price_list'), index('lookup','company',False),
                index('composite','company'), index('composite','shop_name')]
        db = SimpleNamespace(table_exists=Mock(return_value=True), sql=Mock(side_effect=[rows,None]))
        tree = ast.parse(Path('local_commerce/schema/business_structure.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        scope = dict(frappe=SimpleNamespace(db=db))
        exec(compile(tree,'schema','exec'),scope)
        scope['allow_shared_company']()
        self.assertEqual(db.sql.call_args.args[0], 'ALTER TABLE `tabLC Shop` DROP INDEX `company`')
        self.assertEqual(db.sql.call_count,2)

    def test_metadata_allows_shared_company_and_retains_price_list_uniqueness(self):
        import json
        doc=json.loads(Path('local_commerce/local_commerce/doctype/lc_shop/lc_shop.json').read_text())
        fields={f['fieldname']:f for f in doc['fields']}
        self.assertFalse(fields['company'].get('unique'))
        self.assertTrue(fields['selling_price_list']['unique'])
