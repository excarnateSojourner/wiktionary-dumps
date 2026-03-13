import collections.abc
import os.path
import unittest

from test.test_helpers import raw_path, parsed_path

import parsing.sql_helpers
import parsing.etree_helpers
import parsing.parse_stubs
import parsing.parse_redirects
import parsing.parse_cats
import parsing.parse_temps
import parsing.ns
import parsing.lang

class TestSQLHelpers(unittest.TestCase):
	def test_parse_sql(self):
		stub_master = parsing.parse_stubs.StubMaster(parsed_path('stubs.csv'))
		rows: collections.abc.Iterator[tuple] = parsing.sql_helpers.parse_sql(raw_path('page.sql'))
		# Index by ID to eliminate the order of the rows
		actual: dict[int, tuple] = {row[0]: row[1:] for row in rows}
		for stub in stub_master:
			self.assertEqual(actual[stub.id][0], stub.ns, f'Stub ID: {stub.id}')
			self.assertEqual(actual[stub.id][1], stub.title, f'Stub ID: {stub.id}')

if __name__ == '__main__':
	unittest.main()
