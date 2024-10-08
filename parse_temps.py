import argparse
import collections
import collections.abc
import re

import parse_stubs

SQL_VERBOSE_FACTOR = 10 ** 7
TEMPLATE_NAMESPACE = 10
TEMPLATE_PREFIX = 'Template:'

TempData = collections.namedtuple('TempData', ['temp_id', 'temp_title', 'page_id', 'page_title'])

def main():
	parser = argparse.ArgumentParser(description='Converts a templatelinks.sql file to a more readable, flexible form.')
	parser.add_argument('template_links_path', help='Path of the file giving all template links. This file (after decompression) is called "templatelinks.sql" in the database dumps.')
	parser.add_argument('link_targets_path', help='Path of the additional SQL file needed to parse template links. This file (after decompression) is called "linktarget.sql" in the database dumps.')
	parser.add_argument('stubs_path', help='Path of the CSV file containing stubs, as generated by parse_stubs.')
	parser.add_argument('output_path', help='Path of the CSV file to write the parsed templates to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Loading title / id associations...')
	temp_titles_to_ids = {}
	page_ids_to_titles = {}
	pages_count = 0
	for stub in parse_stubs.stubs_gen(args.stubs_path):
		page_ids_to_titles[stub.id] = stub.title
		if stub.ns == TEMPLATE_NAMESPACE:
			temp_titles_to_ids[stub.title.removeprefix(TEMPLATE_PREFIX)] = stub.id

	if args.verbose:
		print(f'Reading link targets:')
	link_targets_to_temp_titles = {}
	for link_targets_count, link_target in enumerate(parse_sql(args.link_targets_path)):
		if int(link_target[1]) == TEMPLATE_NAMESPACE:
			link_targets_to_temp_titles[int(link_target[0])] = clean_page_title(link_target[2])
		if args.verbose and link_targets_count % SQL_VERBOSE_FACTOR == 0:
			print(f'{link_targets_count:,}')

	if args.verbose:
		print(f'Loaded {len(page_ids_to_titles)} page titles and {len(link_targets_to_temp_titles)} temp titles.')
		print('Processing template links:')
	missing_temps = set()
	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for template_links_count, link in enumerate(parse_sql(args.template_links_path)):
			if args.verbose and template_links_count % SQL_VERBOSE_FACTOR * 10 == 0:
				print(f'{template_links_count:,}')
			page_id = int(link[0])
			target_id = int(link[2])
			try:
				temp_title = link_targets_to_temp_titles[target_id]
			except KeyError:
				# Not a template
				continue
			if temp_title.startswith('tracking/'):
				continue
			try:
				temp_id = temp_titles_to_ids[temp_title]
			except KeyError:
				if temp_title not in missing_temps:
					print(f'Warning: Template "{temp_title}" is transcluded but does not exist ({template_links_count:,}).')
					missing_temps.add(temp_title)
				continue
			try:
				page_title = page_ids_to_titles[page_id]
			except KeyError:
				# I found this occurred many times in the 24-07-01 dump.
				continue
			print(f'{temp_id}|{temp_title}|{page_id}|{page_title}', file=out_file)

def temps_gen(templates_path: str) -> collections.abc.Iterator[TempData]:
	with open(templates_path, encoding='utf-8') as temps_file:
		for line in temps_file:
			fields = (line[:-1].split('|', maxsplit=3))
			yield TempData(temp_id=int(fields[0]), temp_title=fields[1], page_id=int(fields[2]), page_title=fields[3])

def parse_sql(path: str, first_n: int = -1) -> collections.abc.Iterator[tuple[str, ...]]:
	with open(path, encoding='utf-8', errors='ignore') as sql_file:
		for line in sql_file:
			if line.startswith('INSERT INTO '):
				try:
					line_trimmed = re.match(r'INSERT INTO `\w*` VALUES \((.*)\);$', line)[1]
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
