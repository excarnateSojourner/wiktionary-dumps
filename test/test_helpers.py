import os.path
import unittest

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
	output_mainspace_pages_prefix = output_path('pages_')
	output_mainspace_english_pages_path = output_path('pages_0_en.xml')
