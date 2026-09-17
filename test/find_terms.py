import itertools
import unittest

import find_terms
import parsing.parse_stubs
import test.test_helpers

class TestTermFilter(test.test_helpers.DumpsTest):
	def setUp(self) -> None:
		self.stub_master = parsing.parse_stubs.StubMaster(self.parsed_stubs_path)
		self.term_filter = find_terms.TermFilter(self.stub_master, self.parsed_mainspace_english_pages_path, 'en', self.parsed_redirects_path)

	def test_check_entry(self):
		expected = {7: True, 8: True}
		mainspace_stubs: list[parsing.parse_stubs.Stub] = list(self.stub_master.all_in_ns(0))
		example_actual_stubs = [str(stub) for stub in itertools.islice(mainspace_stubs, 8)]
		self.assertEqual(len(mainspace_stubs), len(expected), 'Sample of actual stubs:\n' + '\n'.join(example_actual_stubs))
		for stub in mainspace_stubs:
			verdict = self.term_filter.check_entry(stub.id)
			self.assertEqual(verdict, expected.get(stub.id), f'{stub.title} (ID {stub.id}) received a verdict of {verdict} when it should have been {expected.get(stub.id, "[no verdict assigned]")}.')

if __name__ == '__main__':
	test.test_helpers.prepare_data()
	unittest.main()
