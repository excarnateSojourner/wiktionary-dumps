import argparse
import collections
import collections.abc
import re

import parse_stubs

STUBS_VERBOSE_FACTOR = 10 ** 6
SQL_VERBOSE_FACTOR = 400
# Master refers to CategoryMaster
MASTER_VERBOSE_FACTOR = 10 ** 6
# The MediaWiki category namespace ID
CAT_NAMESPACE_ID = 14
CAT_NAMESPACE_PREFIX = 'Category:'

CatLink = collections.namedtuple('CatLink', ['cat_id', 'cat_title', 'page_id', 'page_title'])

def main():
	parser = argparse.ArgumentParser(description='Converts a categorylinks.sql file to a more readable, flexible form.')
	parser.add_argument('sql_path', help='Path of the SQL file giving all category associations. This file (after it is unzipped) is called "categorylinks.sql" in the database dumps.')
	parser.add_argument('stubs_path', help='Path of the CSV file containing page ids, namespaces, and titles, generated by parse_stubs.py.')
	parser.add_argument('output_path', help='Path of the CSV file to write the parsed categories to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Loading stubs:')
	page_titles = {}
	cat_ids = {}
	for stub_count, stub in enumerate(parse_stubs.stubs_gen(args.stubs_path)):
		page_titles[stub.id] = stub.title
		if stub.ns == CAT_NAMESPACE_ID:
			cat_ids[stub.title.removeprefix(CAT_NAMESPACE_PREFIX)] = stub.id
		if args.verbose:
			if stub_count % STUBS_VERBOSE_FACTOR == 0:
				print(f'{stub_count:,}')

	if args.verbose:
		print(f'Loaded {len(page_titles):,} page titles and {len(cat_ids):,} category ids.')
		print('Processing categories (SQL):')
	with open(args.sql_path, encoding='utf-8', errors='ignore') as sql_file:
		with open(args.output_path, 'w', encoding='utf-8') as out_file:
			for sql_count, line in enumerate(sql_file):
				if line.startswith('INSERT INTO '):
					try:
						line_trimmed = re.match(r'INSERT INTO `\w*` VALUES \((.*)\);$', line)[1]
					# no match
					except TypeError:
						continue
					rows = [row.split(',', maxsplit=2)[:2] for row in line_trimmed.split('),(')]
					for row in rows:
						cat_title = row[1].replace('_', ' ').replace("\\'", "'").replace('\\"', '"').removeprefix("'").removesuffix("'")
						page_id = int(row[0])
						try:
							print(f'{cat_ids[cat_title]}|{cat_title}|{page_id}|{page_titles[page_id]}', file=out_file)
						except KeyError:
							# a category may not be found if it is in use but has no page
							pass
				if args.verbose and sql_count % SQL_VERBOSE_FACTOR == 0:
					print(f'{sql_count:,}')

def cats_gen(categories_path: str) -> collections.abc.Iterator[CatLink]:
	with open(categories_path, encoding='utf-8') as cats_file:
		for line in cats_file:
			cat_id, cat_title, page_id, page_title = (line[:-1].split('|', maxsplit=3))
			yield CatLink(int(cat_id), cat_title, int(page_id), page_title)

class Cat():
	def __init__(self):
		# The first set contains the ids of subcategories; the second contains the titles of these same subcategories
		self.subcats = (set(), set())
		# The first set contains the ids of pages; the second contains the titles of these same pages
		self.pages = (set(), set())

	def __str__(self) -> str:
		return f'Category ({len(self.subcats[0])} subcategories and {len(self.pages[0])} pages)'

class CategoryMaster():
	def __init__(self, categories_path: str, verbose: bool = False):
		if verbose:
			print('Loading all categories:')
		self.cats = collections.defaultdict(Cat)
		for count, cat_data in enumerate(cats_gen(categories_path)):
			if cat_data.page_title.startswith(CAT_NAMESPACE_PREFIX):
				self.cats[cat_data.cat_id].subcats[0].add(cat_data.page_id)
				self.cats[cat_data.cat_id].subcats[1].add(cat_data.page_title)
			else:
				self.cats[cat_data.cat_id].pages[0].add(cat_data.page_id)
				self.cats[cat_data.cat_id].pages[1].add(cat_data.page_title)
			if verbose and count % MASTER_VERBOSE_FACTOR == 0:
				print(f'{count:,}')

	def subcats(self, cat_id: int, titles: bool = False) -> set[int] | set[str]:
		return self.cats[cat_id].subcats[1 if titles else 0]

	def pages(self, cat_id: int, titles: bool = False) -> set[int] | set[str]:
		return self.cats[cat_id].pages[1 if titles else 0]

	def descendant_cats(self, cat_id: int, max_depth: int = -1) -> set[int]:
		des_cats = {cat_id}
		if max_depth != 0:
			for subcat in self.subcats(cat_id):
				des_cats |= descendant_cats(subcat, max_depth - 1)
		return des_cats

	def descendant_pages(self, cat_id: int, titles: bool = False, max_depth: int = -1) -> set[int] | set[str]:
		des_pages = set()
		for cat_id in descendant_cats(cat_id, max_depth):
			des_pages |= self.pages(cat_id, titles=titles)
		return des_pages

	def __len__(self):
		return len(self.cats)

if __name__ == '__main__':
	main()
