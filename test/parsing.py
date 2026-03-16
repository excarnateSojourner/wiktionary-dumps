import collections.abc
import re
import unittest
import xml.etree.ElementTree as xet

import wikitextparser

import parsing.sql_helpers
import parsing.etree_helpers
import parsing.parse_stubs
import parsing.parse_redirects
import parsing.parse_cats
import parsing.parse_temps
import parsing.ns
import parsing.lang
import test.test_helpers

class TestSQLHelpers(test.test_helpers.DumpsTest):
	def test_parse_sql(self):
		stub_master = parsing.parse_stubs.StubMaster(self.parsed_stubs_path)
		rows: collections.abc.Iterator[tuple] = parsing.sql_helpers.parse_sql(self.raw_stubs_sql_path)
		# Index by ID to eliminate the order of the rows
		actual: dict[int, tuple] = {row[0]: row[1:] for row in rows}
		for stub in stub_master:
			self.assertEqual(actual[stub.id][0], stub.ns, f'Stub ID: {stub.id}')
			self.assertEqual(actual[stub.id][1], stub.title, f'Stub ID: {stub.id}')

class TestEtreeHelpers(test.test_helpers.DumpsTest):
	def setUp(self):
		# Save just the first <page>
		# Looks like etree_helpers.pages_gen, but does not remove XML namespaces
		self.pages_path = self.raw_pages_path
		for event, elem in xet.iterparse(self.pages_path):
			if re.fullmatch(parsing.etree_helpers.XML_NS_PATTERN + r'page', elem.tag):
				self.example_page = elem
				break

	def test_tag_without_xml_ns_is(self):
		self.assertTrue(parsing.etree_helpers.tag_without_xml_ns_is(self.example_page, 'page'), self.example_page.tag)
		self.assertFalse(parsing.etree_helpers.tag_without_xml_ns_is(self.example_page, 'id'), self.example_page.tag)

	def test_rm_xml_nses(self):
		def assert_no_xml_nses(elem: xet.Element) -> None:
			self.assertFalse(re.match(parsing.etree_helpers.XML_NS_PATTERN, elem.tag), elem.tag)
			for child in elem:
				assert_no_xml_nses(child)

		# We don't have to worry about modifying the example page because it gets recreated separately for each test
		page = parsing.etree_helpers.rm_xml_nses(self.example_page)
		assert_no_xml_nses(page)

	def test_find_child(self):
		id_elem = parsing.etree_helpers.find_child(self.example_page, 'id')
		self.assertEqual(id_elem.text, '1')

	def test_pages_gen(self):
		page_actual = next(parsing.etree_helpers.pages_gen(self.pages_path))
		self.assertEqual(page_actual.tag, self.example_page.tag)
		self.assertEqual(page_actual.text, self.example_page.text)

class TestParseStubs(test.test_helpers.DumpsTest):
	def setUp(self):
		self.stub_master = parsing.parse_stubs.StubMaster(self.parsed_stubs_path)
		self.example_stub = parsing.parse_stubs.Stub(7, 0, 'dermatocyst')

	def test_stub_master_id(self):
		self.assertEqual(self.stub_master.id(self.example_stub.title, self.example_stub.ns), self.example_stub.id)

	def test_stub_master_title(self):
		self.assertEqual(self.stub_master.title(self.example_stub.id), self.example_stub.title)

	def test_stub_master_ns(self):
		self.assertEqual(self.stub_master.ns(self.example_stub.id), self.example_stub.ns)

	def test_stub_master_iter(self):
		stubs = [s for s in self.stub_master if s.id == self.example_stub.id]
		self.assertEqual(stubs, [self.example_stub])

	def test_stubs_gen(self):
		stubs = [s for s in parsing.parse_stubs.stubs_gen(self.parsed_stubs_path) if s.id == self.example_stub.id]
		self.assertEqual(stubs, [self.example_stub])

class TestParseRedirects(test.test_helpers.DumpsTest):
	def setUp(self):
		self.example_redirect = parsing.parse_redirects.RedirectData(6, 10, 'lb', 5, 10, 'label')

	def test_parse_redirects_and_redirects_gen(self):
		parsing.parse_redirects.parse_redirects(self.raw_redirects_path, self.parsed_stubs_path, self.output_redirects_path)
		redirects = [r for r in parsing.parse_redirects.redirects_gen(self.output_redirects_path) if r.src_id == 6]
		self.assertEqual(redirects, [self.example_redirect])

	def test_add_redirects(self):
		with_redirects: set[int] = parsing.parse_redirects.add_redirects({self.example_redirect.dst_id}, self.parsed_redirects_path)
		self.assertIn(self.example_redirect.dst_id, with_redirects)
		self.assertIn(self.example_redirect.src_id, with_redirects)

class TestParseCats(test.test_helpers.DumpsTest):
	def setUp(self):
		self.example_cat_link = parsing.parse_cats.CatLink(2, 'English lemmas', 7, 0, 'dermatocyst')
		self.cat_master = parsing.parse_cats.CategoryMaster(self.parsed_cats_path)

	def test_parse_cats_and_cats_gen(self):
		parsing.parse_cats.parse_cats(self.raw_cats_path, self.parsed_stubs_path, self.output_cats_path)
		gen = parsing.parse_cats.cats_gen(self.output_cats_path)
		cat_links = [c for c in gen if c.cat_id == self.example_cat_link.cat_id and c.page_id == self.example_cat_link.page_id]
		self.assertEqual(cat_links, [self.example_cat_link])

	def test_category_master_subcats(self):
		subcats: set[int] = self.cat_master.subcats(2)
		self.assertEqual(subcats, {3, 4})

	def test_category_master_pages(self):
		pages: set[int] = self.cat_master.pages(2)
		self.assertEqual(pages, {7, 8})

	def test_category_master_descendant_cats(self):
		descendants: set[int] = self.cat_master.descendant_cats(1)
		self.assertEqual(descendants, {1, 2, 3, 4})

	def test_category_master_descendant_pages(self):
		descendants: set[int] = self.cat_master.descendant_pages(1)
		self.assertEqual(descendants, {7, 8})

	def test_category_master_len(self):
		self.assertEqual(len(self.cat_master), 4)

class TestNs(test.test_helpers.DumpsTest):
	def test_namespace_filter(self):
		parsing.ns.namespace_filter(self.raw_articles_path, [[0]], self.output_mainspace_pages_prefix)
		first_page: xet.Element = next(parsing.etree_helpers.pages_gen(self.output_mainspace_pages_prefix + '0.xml'))
		self.assertEqual(parsing.etree_helpers.find_child(first_page, 'ns').text, '0')

class TestLang(test.test_helpers.DumpsTest):
	def setUp(self):
		self.example_lang = 'English'

	def test_language_filter(self):
		parsing.lang.language_filter(self.parsed_mainspace_pages_path, self.output_mainspace_english_pages_path, self.example_lang, self.parsed_cats_path)
		first_page: xet.Element = next(parsing.etree_helpers.pages_gen(self.output_mainspace_english_pages_path))
		text_elem: xet.Element = parsing.etree_helpers.find_child(parsing.etree_helpers.find_child(first_page, 'revision'), 'text')
		wikitext = wikitextparser.parse(text_elem.text)
		sections = wikitext.get_sections(level=2)
		english_sections = [s for s in sections if s.title.strip() == self.example_lang]
		section_titles = [s.title for s in sections]
		self.assertEqual(len(english_sections), 1, msg=f'All level 2 headings: {section_titles}')

if __name__ == '__main__':
	unittest.main()
