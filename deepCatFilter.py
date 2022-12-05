import argparse
import collections
import xml.dom.pulldom

import wikitextparser

import pulldomHelpers

CAT_PREFIX = 'Category:'
# The id of Category:Form-of templates
FORM_OF_TEMP_CAT_ID = 3991887
PAGES_VERBOSITY_FACTOR = 10 ** 4

CatData = collections.namedtuple('CatData', ['catId', 'catTitle', 'pageId', 'pageTitle'])

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('categories_path', help='Path of the parsed categories file that should be used to enumerate subcategories of explicitly mentioned categories.')
	parser.add_argument('output_path', help='Path of the file to write the ids of pages in the categories to.')
	parser.add_argument('-i', '--include', required=True, nargs='+', default=[], help='Categories to include.')
	parser.add_argument('-e', '--exclude', nargs='+', default=[], help='Categories to exclude (overriding includes).')
	parser.add_argument('-n', '--input-ids', action='store_true', help='Indicates that the categories to include and exclude are specified using their ids rather than their names. Specifying ids removes the need for this program to perform time-intensive name-to-id translation.')
	parser.add_argument('-u', '--output-ids', action='store_true', help='Indicates that the output should be given as a list of IDs rather than a list of terms.')
	parser.add_argument('-p', '--pages-path', help='Only intended for mainspace Wiktionary entries. If given, an additional layer of filtering is performed to remove forms of terms that are removed by analyzing their sense lines. This is useful because on Wiktinoary forms (e.g. inflections and alternative forms) often lack the full categorization of their lemmas.')
	parser.add_argument('-t', '--temps-cache-path', help='The path of a file in which to cache (and later retrieve) a list of templates required for form-of filtering (triggered by --pages-path).')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.input_ids:
		includeCats = set(int(i) for i in args.include)
		excludeCats = set(int(i) for i in args.exclude)
	else:
		if args.verbose:
			print('Translating category names to ids...')
		initialIncludes = set(c.removeprefix(CAT_PREFIX) for c in args.include)
		initialExcludes = set(c.removeprefix(CAT_PREFIX) for c in args.exclude)
		includeCats = set()
		excludeCats = set()
		for data in catsGen(args.categories_path):
			if data.catTitle in initialIncludes:
				includeCats.add(data.catId)
				initialIncludes.remove(data.catTitle)
			if data.catTitle in initialExcludes:
				excludeCats.add(data.catId)
				initialExcludes.remove(data.catTitle)
		if initialIncludes or initialExcludes:
			print('I was unable to find any pages in the following categories. This either means they do not exist (check your spelling) or they are empty.')
			print(', '.join(initialIncludes | initialExcludes))
		print('If you want to include and exclude the same sets of categories later, and you want to provide their IDs instead of titles (so I do not have to translate to IDs for you), here are the IDs formatted as command-line arguments:')
		print('-i ' + ' '.join(str(i) for i in includeCats) + ' -e ' + ' '.join(str(e) for e in excludeCats) + ' -n')

	terms = catFilter(args.categories_path, includeCats, excludeCats, returnTitles=not args.output_ids, verbose=args.verbose)
	if args.pages_path:
		terms = formOfFilter(terms, args.categories_path, args.pages_path, args.temps_cache_path, verbose=args.verbose)

	with open(args.output_path, 'w') as outFile:
		for term in terms:
			print(term, file=outFile)

def catFilter(categories_path, includeCats, excludeCats, returnTitles=False, verbose=False):
	if verbose:
		print('Looking for pages and subcategories in specified categories:')
	# collect subcats to process in the next round
	nextIncludeCats = set()
	nextExcludeCats = set()
	# collect non-cat pages in cats
	includePages = set()
	excludePages = set()

	depth = 0
	while includeCats or excludeCats:
		if verbose:
			print('', '-' * 10, f'Round {depth}', '-' * 10, sep='\n')
		for data in catsGen(categories_path):
			if data.catId in includeCats:
				if data.pageTitle.startswith(CAT_PREFIX):
					nextIncludeCats.add(data.pageId)
					if verbose:
						print(f'including "{data.pageTitle.removeprefix(CAT_PREFIX)}"')
				elif returnTitles:
					includePages.add(data.pageTitle)
				else:
					includePages.add(data.pageId)
			if data.catId in excludeCats:
				if data.pageTitle.startswith(CAT_PREFIX):
					nextExcludeCats.add(data.pageId)
					if verbose:
						print(f'excluding "{data.pageTitle.removeprefix(CAT_PREFIX)}"')
				elif returnTitles:
					excludePages.add(data.pageTitle)
				else:
					excludePages.add(data.pageId)
		includeCats = nextIncludeCats
		excludeCats = nextExcludeCats
		nextIncludeCats = set()
		nextExcludeCats = set()
		depth += 1

	return includePages - excludePages

def formOfFilter(terms, categories_path, pages_path, temps_cache_path=None, verbose=False):
	if temps_cache_path:
		try:
			with open(temps_cache_path) as tempsCacheFile:
				formOfTemps = set(tempsCacheFile.read().splitlines())
		except FileNotFoundError:
			formOfTemps = {temp.removeprefix('Template:') for temp in catFilter(categories_path, {FORM_OF_TEMP_CAT_ID}, set(), returnTitles=True)}
			with open(temps_cache_path, 'w') as tempsCacheFile:
				for temp in formOfTemps:
					print(temp, file=tempsCacheFile)
	else:
		formOfTemps = {temp.removeprefix('Template:') for temp in catFilter(categories_path, {FORM_OF_TEMP_CAT_ID}, set(), returnTitles=True)}

	doc = xml.dom.pulldom.parse(pages_path)
	pageContents = {}

	if verbose:
		print('Loading pages data:')
	count = 0
	for event, node in doc:
		if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'title':
			doc.expandNode(node)
			term = pulldomHelpers.getText(node)
			if term in terms:
				textNode = next(n for e, n in doc if e == xml.dom.pulldom.START_ELEMENT and n.tagName == 'text')
				doc.expandNode(textNode)
				pageContents[term] = pulldomHelpers.getText(textNode)

			if verbose and count % PAGES_VERBOSITY_FACTOR == 0:
				print(count)
			count += 1

	if verbose:
		print('Checking forms...')
	for term, text in pageContents.items():
		if not checkTerm(term, text, terms, formOfTemps):
			terms.remove(term)

	return terms

def checkTerm(term, text, terms, formOfTemps):
	for line in text.splitlines():
		if line.startswith('# '):
			temps = wikitextparser.parse(line).templates
			try:
				formOfTemp = next(t for t in temps if t.normal_name() in formOfTemps)
				mainForm = (formOfTemp.get_arg('2') or formOfTemp.get_arg('1')).value
				if mainForm in terms:
					return True
			except StopIteration:
				return True

	return False

def catsGen(categories_path):
	with open(categories_path) as catsFile:
		for line in catsFile:
			fields = (line[:-1].split(',', maxsplit=3))
			yield CatData(catId=int(fields[0]), catTitle=fields[1], pageId=int(fields[2]), pageTitle=fields[3])

if __name__ == '__main__':
	main()
