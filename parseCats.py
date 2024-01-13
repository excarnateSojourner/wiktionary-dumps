import argparse
import collections
import re
from typing import Iterator
import xml.dom.pulldom

import parseStubs
import pulldomHelpers

STUBS_VERBOSE_FACTOR = 10 ** 6
SQL_VERBOSE_FACTOR = 400
CATEGORY_NAMESPACE = 14
CATEGORY_PREFIX = 'Category:'

CatData = collections.namedtuple('CatData', ['catId', 'catTitle', 'pageId', 'pageTitle'])

def main():
	parser = argparse.ArgumentParser('Converts a categorylinks.sql file to a more readable, flexible form.')
	parser.add_argument('sql_path', help='Path of the SQL file giving all category associations. This file (after it is unzipped) is called "categorylinks.sql" in the database dumps.')
	parser.add_argument('stubs_path', help='Path of the CSV file containing page ids, namespaces, and titles, generated by parseStubs.py.')
	parser.add_argument('output_path', help='Path of the CSV file to write the parsed categories to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Loading stubs:')
	pageTitles = {}
	catIds = {}
	for stubCount, stub in enumerate(parseStubs.stubsGen(args.stubs_path)):
		pageTitles[stub.id] = stub.title
		if stub.ns == CATEGORY_NAMESPACE:
			catIds[stub.title.removeprefix(CATEGORY_PREFIX)] = stub.id
		if args.verbose:
			if stubCount % STUBS_VERBOSE_FACTOR == 0:
				print(stubCount)

	if args.verbose:
		print(f'Loaded {len(pageTitles)} page titles and {len(catIds)} category ids.')
		print('Processing categories (SQL):')
	with open(args.sql_path, encoding='utf-8', errors='ignore') as sqlFile:
		with open(args.output_path, 'w', encoding='utf-8') as outFile:
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
						pageId = int(row[0])
						try:
							print(f'{catIds[catTitle]}|{catTitle}|{pageId}|{pageTitles[pageId]}', file=outFile)
						except KeyError:
							# a category may not be found if it is in use but has no page
							pass
				if args.verbose and sqlCount % SQL_VERBOSE_FACTOR == 0:
					print(sqlCount)

def catsGen(categories_path: str) -> Iterator[CatData]:
	with open(categories_path, encoding='utf-8') as catsFile:
		for line in catsFile:
			fields = (line[:-1].split('|', maxsplit=3))
			yield CatData(catId=int(fields[0]), catTitle=fields[1], pageId=int(fields[2]), pageTitle=fields[3])

if __name__ == '__main__':
	main()
