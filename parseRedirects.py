import argparse
import collections
import re
from typing import Iterator
import xml.dom.pulldom

import pulldomHelpers

PAGES_VERBOSE_FACTOR = 10 ** 5
SQL_VERBOSE_FACTOR = 400

RedirectData = collections.namedtuple('RedirectData', ['srcId', 'srcTitle', 'dstId', 'dstTitle'])

def main():
	parser = argparse.ArgumentParser('Converts a redirect.sql to a more readable, flexible form.')
	parser.add_argument('sql_path', help='Path of the file giving all redirects. This file (after it is unzipped) is called "redirect.sql" in the database dumps.')
	parser.add_argument('pages_path', help='Path of the pages file containing title / id associations for all pages (in all namespaces) that may be the source or destination of a redirect. The best file for this from the database dumps is "stub-meta-current.xml".')
	parser.add_argument('parsed_path', help='Path of the CSV file to write the parsed redirects to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Loading namespace prefixes...')
	nsTitles = pulldomHelpers.getNamespaceTitles(args.pages_path)

	if args.verbose:
		print('Loading title / id associations:')
	# ids and titles map the exact same data in opposite directions
	titles = {}
	ids = {}
	for pageCount, page in enumerate(pulldomHelpers.getPageDescendantText(args.pages_path, ['title', 'id'])):
		titles[page['id']] = page['title']
		ids[page['title']] = page['id']
		if args.verbose and pageCount % PAGES_VERBOSE_FACTOR == 0:
			print(pageCount)

	if args.verbose:
		print('Reading redirect data (SQL) and writing output...')
	with open(args.sql_path, encoding='utf-8', errors='ignore') as sqlFile:
		with open(args.parsed_path, 'w', encoding='utf-8') as outFile:
			for sqlCount, line in enumerate(sqlFile):
				if line.startswith('INSERT INTO '):
					try:
						lineTrimmed = re.match('INSERT INTO `\w*` VALUES \((.*)\);$', line)[1]
					# no match
					except TypeError:
						continue
					rows = [row.split(',', maxsplit=4)[:4] for row in lineTrimmed.split('),(')]
					for row in rows:
						# if an internal redirect
						if len(row[3]) == 2:
							dstTitle = nsTitles[int(row[1])] + ':' + row[2].replace('_', ' ').replace("\\'", "'").replace('\\"', '"').removeprefix("'").removesuffix("'")
							try:
								print(f'{row[0]}|{titles[row[0]]}|{ids[dstTitle]}|{dstTitle}', file=outFile)
							except KeyError:
								# broken redirect
								pass

				if args.verbose and sqlCount % SQL_VERBOSE_FACTOR == 0:
					print(sqlCount)

def redirectsGen(path: str) -> Iterator[RedirectData]:
	with open(path, encoding='utf-8') as inFile:
		for line in inFile:
			fields = (line[:-1].split('|'))
			yield RedirectData(srcId=int(fields[0]), srcTitle=fields[1], dstId=int(fields[2]), dstTitle=fields[3])

if __name__ == '__main__':
	main()
