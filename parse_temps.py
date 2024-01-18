import argparse
import collections
import re
import xml.dom.pulldom

import pulldom_helpers

PAGES_VERBOSE_FACTOR = 10 ** 4
SQL_VERBOSE_FACTOR = 10 ** 6
TEMPLATE_NAMESPACE = 10
TEMPLATE_PREFIX = 'Template:'

TempData = collections.namedtuple('TempData', ['temp_id', 'temp_title', 'page_id', 'page_title'])

def main():
	parser = argparse.ArgumentParser(description='Converts a templatelinks.sql file to a more readable, flexible form.')
	parser.add_argument('template_links_path', help='Path of the file giving all template links. This file (after decompression) is called "templatelinks.sql" in the database dumps.')
	parser.add_argument('link_targets_path', help='Path of the additional SQL file needed to parse template links. This file (after decompression) is called "linktarget.sql" in the database dumps.')
	parser.add_argument('pages_titles_path', help='Path of the SQL file or pages file containing title / id associations for pages (in all namespaces, including templates). The best files for this from the database dumps (after decompressing) are "page.sql" and "stub-meta-current.xml".')
	parser.add_argument('parsed_path', help='Path of the CSV file to write the parsed templates to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Loading title / id associations...')
	temp_titles_to_ids = {}
	page_ids_to_titles = {}
	pages_count = 0
	if args.pages_titles_path.endswith('.sql'):
		for page in parse_sql(args.pages_titles_path, first_n=3):
			page_title = clean_page_title(page[2])
			page_ids_to_titles[page[0]] = page_title
			if int(page[1]) == TEMPLATE_NAMESPACE:
				temp_titles_to_ids[page_title.removeprefix(TEMPLATE_PREFIX)] = page[0]
			if args.verbose:
				if pages_count % SQL_VERBOSE_FACTOR == 0:
					print(f'{pages_count:,}')
				pages_count += 1
	elif args.pages_titles_path.endswith('.xml'):
		for page in pulldom_helpers.get_page_descendant_text(args.pages_titles_path, ['title', 'ns', 'id']):
			page_ids_to_titles[page['id']] = page['title']
			if int(page['ns']) == TEMPLATE_NAMESPACE:
				temp_titles_to_ids[page['title'].removeprefix(TEMPLATE_PREFIX)] = page['id']
			if args.verbose:
				if pages_count % PAGES_VERBOSE_FACTOR == 0:
					print(f'{pages_count:,}')
				pages_count += 1
	else:
		raise ValueError(f'The extension of --pages-titles-path does not identify it as an XML file (.xml) or an SQL file (.sql).')

	if args.verbose:
		print(f'Reading link targets:')
	link_targets_to_temp_titles = {}
	for link_targets_count, link_target in enumerate(parse_sql(args.link_targets_path)):
		link_targets_to_temp_titles[link_target[0]] = (clean_page_title(link_target[2]), int(link_target[1]) == TEMPLATE_NAMESPACE)
		if args.verbose and link_targets_count % SQL_VERBOSE_FACTOR == 0:
			print(f'{link_targets_count:,}')

	if args.verbose:
		print(f'Loaded {len(page_ids_to_titles)} page titles and {len(link_targets_to_temp_titles)} temp titles.')
		print('Processing categories (SQL):')
	with open(args.parsed_path, 'w', encoding='utf-8') as out_file:
		for template_links_count, link in enumerate(parse_sql(args.template_links_path)):
			if args.verbose and template_links_count % SQL_VERBOSE_FACTOR * 10 == 0:
				print(f'{template_links_count:,}')
			try:
				temp_title, is_temp_ns = link_targets_to_temp_titles[link[2]]
			except KeyError:
				print(f'[{template_links_count:,}:] Link target {link[2]} not found in linktarget.sql.')
				continue
			if temp_title.startswith('tracking/') or not is_temp_ns:
				continue
			try:
				temp_id = temp_titles_to_ids[temp_title]
			except KeyError:
				print(f'[{template_links_count:,}:] Template {temp_title} is transcluded but does not exist.')
				continue
			page_id = link[0]
			try:
				page_title = page_ids_to_titles[page_id]
			except KeyError:
				print(f'[{template_links_count:,}:] Page with id {page_id} not found in page.sql.')
				continue
			print(f'{temp_id},{temp_title},{page_id},{page_title}', file=out_file)

def temps_gen(templates_path: str) -> collections.abc.Iterator[TempData]:
	with open(templates_path, encoding='utf-8') as temps_file:
		for line in temps_file:
			fields = (line[:-1].split(',', maxsplit=3))
			yield TempData(temp_id=int(fields[0]), temp_title=fields[1], page_id=int(fields[2]), page_title=fields[3])

def parse_sql(path: str, first_n: int = -1) -> collections.abc.Iterator[tuple[str]]:
	with open(path, encoding='utf-8', errors='ignore') as sql_file:
		for line in sql_file:
			if line.startswith('INSERT INTO '):
				try:
					line_trimmed = re.match('INSERT INTO `\w*` VALUES \((.*)\);$', line)[1]
				# no match
				except TypeError:
					continue
				if first_n <= 0:
					rows = [row.split(',') for row in line_trimmed.split('),(')]
				else:
					rows = [row.split(',', maxsplit=first_n + 1)[:first_n] for row in line_trimmed.split('),(')]
				for row in rows:
					yield row

def clean_page_title(title: str) -> str:
	return title.replace('_', ' ').replace("\\'", "'").replace('\\"', '"').removeprefix("'").removesuffix("'")

if __name__ == '__main__':
	main()
