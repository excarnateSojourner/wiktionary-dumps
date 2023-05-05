import argparse
import collections
import re
from typing import Iterator
import xml.dom.pulldom

import pulldomHelpers

PAGES_VERBOSE_FACTOR = 10 ** 4
SQL_VERBOSE_FACTOR = 400
CATEGORY_NAMESPACE = 14
CATEGORY_PREFIX = 'Category:'

CatData = collections.namedtuple('CatData', ['catId', 'catTitle', 'pageId', 'pageTitle'])

def main():
	parser = argparse.ArgumentParser('Converts a categorylinks.sql file to a more readable, flexible form.')
	parser.add_argument('sql_path', help='Path of the file giving all category associations. This file (after it is unzipped) is called "categorylinks.sql" in the database dumps.')
	parser.add_argument('pages_path', help='Path of the pages file containing title / id associations for pages (in all namespaces, including categories). The best file for this from the database dumps is "stub-meta-current.xml".')
	parser.add_argument('parsed_path', help='Path of the CSV file to write the parsed categories to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Loading title / id associations...')
	pageTitles = {}
	catIds = {}
	pagesCount = 0
	for page in pulldomHelpers.getPageDescendantText(args.pages_path, ['title', 'id', 'ns']):
		pageTitles[page['id']] = page['title']
		if int(page['ns']) == CATEGORY_NAMESPACE:
			catIds[page['title'].removeprefix(CATEGORY_PREFIX)] = page['id']
		if args.verbose:
			if pagesCount % PAGES_VERBOSE_FACTOR == 0:
				print(pagesCount)
			pagesCount += 1

	if args.verbose:
		print(f'Loaded {len(pageTitles)} page titles and {len(catIds)} category ids.')
		print('Processing categories (SQL):')
	with open(args.sql_path, encoding='utf-8', errors='ignore') as sqlFile:
		with open(args.parsed_path, 'w', encoding='utf-8') as outFile:
			for sqlCount, line in enumerate(sqlFile):
				if line.startswith('INSERT INTO '):
					try:
						lineTrimmed = re.match('INSERT INTO `\w*` VALUES \((.*)\);$', line)[1]
					# no match
					except TypeError:
						continue
					rows = [row.split(',', maxsplit=2)[:2] for row in lineTrimmed.split('),(')]
					for row in rows:
						catTitle = row[1].replace('_', ' ').replace("\\'", "'").replace('\\"', '"').removeprefix("'").removesuffix("'")
						pageId = row[0]
						try:
							print(f'{catIds[catTitle]},{catTitle},{pageId},{pageTitles[pageId]}', file=outFile)
						except KeyError:
							# a category may not be found if it is in use but has no page
							pass
				if args.verbose and sqlCount % SQL_VERBOSE_FACTOR == 0:
					print(sqlCount)

def catsGen(categories_path: str) -> Iterator[CatData]:
	with open(categories_path, encoding='utf-8') as catsFile:
		for line in catsFile:
			fields = (line[:-1].split(',', maxsplit=3))
			yield CatData(catId=int(fields[0]), catTitle=fields[1], pageId=int(fields[2]), pageTitle=fields[3])

if __name__ == '__main__':
	main()
