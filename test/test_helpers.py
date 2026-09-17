import os.path
import unittest

import parsing.parse_stubs
import parsing.parse_redirects
import parsing.parse_cats
import parsing.ns
import parsing.lang

SCRIPT_DIR = os.path.dirname(__file__)

class DumpsTest(unittest.TestCase):

	@staticmethod
	def raw_path(*parts: str) -> str:
		return os.path.join(SCRIPT_DIR, 'raw_data', *parts)

	@staticmethod
	def parsed_path(*parts: str) -> str:
		return os.path.join(SCRIPT_DIR, 'parsed_data', *parts)

	@staticmethod
	def output_path(*parts: str) -> str:
		return os.path.join(SCRIPT_DIR, 'output_data', *parts)

	raw_stubs_sql_path = raw_path('page.sql')
	raw_stubs_xml_path = raw_path('stubs-meta-current.xml')
	raw_link_targets_path = raw_path('linktarget.sql')
	raw_redirects_path = raw_path('redirect.sql')
	raw_cats_path = raw_path('categorylinks.sql')
	raw_pages_path = raw_path('pages-meta-current.xml')
	raw_articles_path = raw_path('pages-articles.xml')

	parsed_stubs_path = parsed_path('stubs.csv')
	parsed_redirects_path = parsed_path('redirects.csv')
	parsed_cats_path = parsed_path('cats.csv')
	parsed_mainspace_pages_path = parsed_path('pages_0.xml')
	parsed_mainspace_english_pages_path = parsed_path('pages_0_en.xml')

	output_stubs_path = output_path('stubs.csv')
	output_redirects_path = output_path('redirects.csv')
	output_cats_path = output_path('cats.csv')
	# ns.namespace_filter automatically appends the namespace ID and the file extension
	output_mainspace_pages_path = output_path('pages_0.xml')
	output_mainspace_english_pages_path = output_path('pages_0_en.xml')

def prepare_data() -> None:
	dt = DumpsTest
	parsing.parse_stubs.parse_stubs(dt.raw_stubs_sql_path, dt.parsed_stubs_path)
	parsing.parse_redirects.parse_redirects(dt.raw_redirects_path, dt.parsed_stubs_path, dt.parsed_redirects_path)
	parsing.parse_cats.parse_cats(dt.raw_cats_path, dt.parsed_stubs_path, dt.raw_link_targets_path, dt.parsed_cats_path)
	parsing.ns.namespace_filter(dt.raw_articles_path, namespace_groups=[[0]], output_path_prefix=dt.parsed_mainspace_pages_path.removesuffix('0.xml'))
	parsing.lang.language_filter(dt.parsed_mainspace_pages_path, dt.parsed_mainspace_english_pages_path, 'English', dt.parsed_cats_path)
