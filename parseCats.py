# Cleans up a categorylinks.sql file so that it can be read as comma separated category-page pairs.

import argparse
import re
import xml.dom.pulldom

import pulldomHelpers

PAGES_VERBOSE_FACTOR = 10 ** 4
SQL_VERBOSE_FACTOR = 400
CATEGORY_NAMESPACE = 14
CATEGORY_PREFIX = 'Category:'

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('sql_path', help='Path of the file giving all category associations. This file is called "categorylinks.sql" in the database dumps.')
	parser.add_argument('pages_path', help='Path of the pages file containing title / id associations for pages (in all namespaces, including categories). The best file for this from the database dumps is "stub-meta-current.xml".')
	parser.add_argument('parsed_path', help='Path of the CSV file to write the parsed categories to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Loading title / id associations...')
	pageTitles = {}
	catIds = {}
	doc = xml.dom.pulldom.parse(args.pages_path)
	pagesCount = 0
	for event, node in doc:
		if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'page':
			doc.expandNode(node)
			pageTitle = pulldomHelpers.getDescendantContent(node, 'title')
			pageId = pulldomHelpers.getDescendantContent(node, 'id')
			pageTitles[pageId] = pageTitle
			if int(pulldomHelpers.getDescendantContent(node, 'ns')) == CATEGORY_NAMESPACE:
				catIds[pageTitle.removeprefix(CATEGORY_PREFIX)] = pageId
			if args.verbose:
				if pagesCount % PAGES_VERBOSE_FACTOR == 0:
					print(pagesCount)
				pagesCount += 1

	if args.verbose:
		print(f'Loaded {len(pageTitles)} page titles and {len(catIds)} category ids.')
		print('Processing categories (SQL):')
	with open(args.sql_path, encoding='utf-8', errors='ignore') as sqlFile:
		with open(args.parsed_path, 'w', encoding='utf-8') as pairsFile:
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
							print(f'{catIds[catTitle]},{catTitle},{pageId},{pageTitles[pageId]}', file=pairsFile)
						except KeyError:
							# a category may not be found if it is in use but has no page
							pass
				if args.verbose and sqlCount % SQL_VERBOSE_FACTOR == 0:
					print(sqlCount)

if __name__ == '__main__':
	main()
