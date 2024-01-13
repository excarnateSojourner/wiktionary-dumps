import argparse
import collections
import re
from typing import Iterator
import xml.dom.pulldom

import parseStubs
import pulldomHelpers

STUBS_VERBOSE_FACTOR = 10 ** 6
SQL_VERBOSE_FACTOR = 400

RedirectData = collections.namedtuple('RedirectData', ['srcId', 'srcTitle', 'dstId', 'dstTitle'])

def main():
	parser = argparse.ArgumentParser('Converts a redirect.sql to a more readable, flexible form.')
	parser.add_argument('sql_path', help='Path of the file giving all redirects. This file (after it is unzipped) is called "redirect.sql" in the database dumps.')
	parser.add_argument('stubs_path', help='Path of the CSV file containing page ids, namespaces, and titles, genrated by parseStubs.py. Must contain all pages (in all namespaces) that may be the source or destination of a redirect.')
	parser.add_argument('pages_path', help='Path of the XML file containing the ids and titles of Wiktionary namespaces. This is used to add the namespace prefixes to the titles of redirect destinations (as the SQL does not have them). Any of the following files in the dumps will work equally well for this: stub-meta-current.xml, pages-articles.xml, pages-meta-current.xml.')
	parser.add_argument('output_path', help='Path of the CSV file to write the parsed redirects to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Loading namespace prefixes...')
	nsTitles = pulldomHelpers.getNamespaceTitles(args.pages_path)

	if args.verbose:
		print('Loading ids and titles:')
	# ids and titles map the exact same data in opposite directions
	titles = {}
	ids = {}
	for pageCount, page in enumerate(parseStubs.stubsGen(args.stubs_path)):
		titles[page.id] = page.title
		ids[page.title] = page.id
		if args.verbose and pageCount % STUBS_VERBOSE_FACTOR == 0:
			print(pageCount)

	if args.verbose:
		print('Reading redirect data (SQL) and writing output:')
	with open(args.sql_path, encoding='utf-8', errors='ignore') as sqlFile:
		with open(args.output_path, 'w', encoding='utf-8') as outFile:
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
								print(f'{row[0]}|{titles[int(row[0])]}|{ids[dstTitle]}|{dstTitle}', file=outFile)
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
