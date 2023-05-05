import argparse
import collections
from typing import Iterator, Optional, Union
import xml.dom.pulldom

import wikitextparser

import parseCats
import pulldomHelpers

PAGES_VERBOSITY_FACTOR = 10 ** 4
CAT_PREFIX = 'Category:'
# The id of Category:Form-of templates
FORM_OF_TEMP_CAT_ID = 3991887
LABEL_TEMPS = {'label', 'lb', 'lbl'}

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('categories_path', help='Path of the parsed categories file that should be used to enumerate subcategories of explicitly mentioned categories.')
	parser.add_argument('output_path', help='Path of the file to write the ids of pages in the categories to.')
	parser.add_argument('-i', '--include', required=True, nargs='+', default=[], help='Categories to include.')
	parser.add_argument('-e', '--exclude', nargs='+', default=[], help='Categories to exclude (overriding includes).')
	parser.add_argument('-n', '--input-ids', action='store_true', help='Indicates that the categories to include and exclude are specified using their ids rather than their names. Specifying ids removes the need for this program to perform time-intensive name-to-id translation.')
	parser.add_argument('-u', '--output-ids', action='store_true', help='Indicates that the output should be given as a list of IDs rather than a list of terms. Ignored if --pages-path is given (indicating that the text of entries should be processed as well).')
	parser.add_argument('-p', '--pages-path', help='Only intended for mainspace Wiktionary entries. If given, an additional layer of filtering is performed to remove forms of terms that are removed by analyzing their sense lines. This is useful because on Wiktionary forms (e.g. inflections and alternative forms) often lack the full categorization of their lemmas.')
	parser.add_argument('-t', '--temps-cache-path', help='The path of a file in which to cache (and later retrieve) a list of templates required for form-of filtering (triggered by --pages-path).')
	parser.add_argument('-l', '--label-lang', help='The ISO 639 code of the language for which to exclude labels. Has no effect unless --exclude-labels is also given.')
	parser.add_argument('-x', '--exclude-labels', nargs='+', default=[], help='Labels are positional arguments of the {{label}} (AKA {{lb}}) template (excluding the language code). Requires --label-lang.')
	parser.add_argument('-m', '--exclude-temps', nargs='+', default=[], help='Templates that should cause terms to be exluded.')
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
		for data in parseCats.catsGen(args.categories_path):
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

	terms = catFilter(args.categories_path, includeCats, excludeCats, returnTitles=not args.output_ids and not args.pages_path, verbose=args.verbose)
	if args.pages_path:
		terms = entryTextFilter(terms, args.categories_path, args.pages_path, args.label_lang, args.exclude_labels, args.exclude_temps, args.temps_cache_path, verbose=args.verbose)

	with open(args.output_path, 'w', encoding='utf-8') as outFile:
		for term in terms:
			print(term, file=outFile)

def catFilter(categories_path: str, includeCats: set[int], excludeCats: set[int], returnTitles: bool = False, verbose: bool = False) -> Union[set[int], set[str]]:
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
		for data in parseCats.catsGen(categories_path):
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

def entryTextFilter(terms: set[str], categories_path: str, pages_path: str, label_lang: str, exclude_labels: set[str], exclude_temps: set[str], temps_cache_path: Optional[str] = None, verbose: bool = False) -> set[str]:

	if temps_cache_path:
		try:
			with open(temps_cache_path, encoding='utf-8') as tempsCacheFile:
				formOfTemps = set(tempsCacheFile.read().splitlines())
		except FileNotFoundError:
			formOfTemps = findFormOfTemps(categories_path)
			with open(temps_cache_path, 'w', encoding='utf-8') as tempsCacheFile:
				for temp in formOfTemps:
					print(temp, file=tempsCacheFile)
	else:
		formOfTemps = findFormOfTemps(categories_path)

	senseLines = findSenseLines(terms, pages_path, verbose)

	if verbose:
		print('Checking forms...')
	for term in senseLines:
		if not checkTerm(term, senseLines, formOfTemps, excludeLabels, excludeTemps):
			terms.remove(term)

	return terms

def findFormOfTemps(categories_path: str) -> set[str]:
	return {temp.removeprefix('Template:') for temp in catFilter(categories_path, {FORM_OF_TEMP_CAT_ID}, set(), returnTitles=True)}

def findSenseLines(terms: set[str], pages_path: str, verbose: bool = False) -> dict[str, list[str]]:
	doc = xml.dom.pulldom.parse(pages_path)
	senseLines = {}

	if verbose:
		print('\nLoading pages data:')
	count = 0
	for event, node in doc:
		if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'title':
			doc.expandNode(node)
			term = pulldomHelpers.getText(node)
			if term in terms:
				textNode = next(n for e, n in doc if e == xml.dom.pulldom.START_ELEMENT and n.tagName == 'text')
				doc.expandNode(textNode)
				senseLines[term] = [li for li in pulldomHelpers.getText(textNode).splitlines() if li.startswith('# ')]

			if verbose and count % PAGES_VERBOSITY_FACTOR == 0:
				print(count)
			count += 1
	return senseLines

def checkTerm(term: set[str], senseLines: dict[str, list[str]], formOfTemps: set[str], excludeLabels: set[str], excludeTemps: set[str]) -> bool:
	print(f'DEBUG: checking {term}')
	for line in senseLines[term]:
		temps = wikitextparser.parse(line).templates
		try:
			formOfTemp = next(t for t in temps if t.normal_name() in formOfTemps)
			mainForm = (formOfTemp.get_arg('2') or formOfTemp.get_arg('1')).value
			if mainForm not in senseLines or not checkTerm(mainForm, senseLines, formOfTemps, excludeLabels, excludeTemps):
				continue
		except StopIteration:
			pass
		try:
			labelTemp = next(t for t in temps if t.normal_name() in LABEL_TEMPS and t.arguments[0].positional and t.get_arg('1').value == 'en')
			labels = {a.value for a in labelTemp.arguments[1:] if a.positional}
			if not labels.isdisjoint(excludeLabels):
				continue
		except StopIteration:
			pass
		if any(temp.normal_name() in excludeTemps for temp in temps):
			continue
		return True
	return False

if __name__ == '__main__':
	main()
