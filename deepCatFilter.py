import argparse
import collections
from typing import Optional, Union
import xml.dom.pulldom

import wikitextparser

import parseCats
import parseRedirects
import parseStubs
import pulldomHelpers

PAGES_VERBOSITY_FACTOR = 10 ** 4
CAT_PREFIX = 'Category:'
TEMP_PREFIX = 'Template:'
# The ID of Category:Form-of templates
FORM_OF_TEMP_CAT_ID = 3991887
LABEL_TEMPS = {'label', 'lb', 'lbl'}

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('categories_path', help='Path of the parsed categories file that should be used to enumerate subcategories of explicitly mentioned categories.')
	parser.add_argument('output_path', help='Path of the file to write the IDs of pages in the categories to.')
	parser.add_argument('-i', '--include', required=True, nargs='+', default=[], help='Categories to include. These can either all be given as page titles, in which case --stubs-path is required to convert them to page ids, or they can all be given as page IDs (in which case --stubs-path must *not* be given).')
	parser.add_argument('-e', '--exclude', nargs='+', default=[], help='Categories to exclude (overriding includes).')
	parser.add_argument('-s', '--stubs-path', help='Path of the CSV file (as produced by parseStubs.py) containing page IDs and titles. If given, this indicates that the categories to include and exclude have been specified using their IDs rather than their names. Specifying IDs removes the need for this program to perform time-intensive name-to-id translation.')
	parser.add_argument('-u', '--output-ids', action='store_true', help='Indicates that the output should be given as a list of IDs rather than a list of terms. Ignored if --pages-path is given (indicating that the text of entries should be processed as well).')
	parser.add_argument('-d', '--depth', default=-1, type=int, help='The maximum depth to explore each category\'s descendants. Zero means just immediate children, one means children and grandchildren, etc. A negative value means no limit.')
	parser.add_argument('-p', '--pages-path', help='Only intended for mainspace Wiktionary entries. If given, an additional layer of filtering is performed to remove forms of terms that are removed by analyzing their sense lines. This is useful because on Wiktionary forms (e.g. inflections and alternative forms) often lack the full categorization of their lemmas.')
	parser.add_argument('-r', '--redirects-path', help='The path of the CSV redirects file produced by parseRedirects.py. Ignored if --pages-path is not given.')
	parser.add_argument('-t', '--temps-cache-path', help='The path of a file in which to cache (and later retrieve) a list of templates required for form-of filtering (triggered by --pages-path).')
	parser.add_argument('-l', '--label-lang', default='en', help='The Wiktionary language code (usually the ISO 639 code) of the language for which to exclude labels. Ignored if --exclude-labels is not also given.')
	parser.add_argument('-x', '--exclude-labels', nargs='+', default=[], help='Labels are positional arguments of the {{label}} (AKA {{lb}}) template (excluding the language code). Requires --label-lang.')
	parser.add_argument('-m', '--exclude-temps', nargs='+', default=[], help='If a given template given here is used in a sense of a term, that sense will not support the inclusion of the term. (The term may still be included if it has other "valid" senses.)')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.stubs_path:
		if args.verbose:
			print('Translating category names to ids...')
		initial_includes = set((c if c.startswith(CAT_PREFIX) else CAT_PREFIX + c) for c in args.include)
		initial_excludes = set((c if c.startswith(CAT_PREFIX) else CAT_PREFIX + c) for c in args.exclude)
		include_cats = set()
		exclude_cats = set()

		for stub in parseStubs.stubsGen(args.stubs_path):
			if stub.title in initial_includes:
				include_cats.add(stub.id)
				initial_includes.remove(stub.title)
			if stub.title in initial_excludes:
				exclude_cats.add(stub.id)
				initial_excludes.remove(stub.title)
		if initial_includes or initial_excludes:
			print('I was unable to find pages for the following categories. This either means they do not exist (check your spelling) or the category page has not been created.')
			print(', '.join(initial_includes | initial_excludes))
		print('If you want to include and exclude the same sets of categories later, and you want to provide their IDs instead of titles (so I do not have to translate to IDs for you), here are the IDs formatted as command-line arguments:')
		print('-i ' + ' '.join(str(i) for i in include_cats) + ' -e ' + ' '.join(str(e) for e in exclude_cats))
	else:
		include_cats = set(int(i) for i in args.include)
		exclude_cats = set(int(i) for i in args.exclude)

	terms = catFilter(args.categories_path, include_cats, exclude_cats, return_titles=not args.output_ids or args.pages_path, max_depth=args.depth, verbose=args.verbose)
	if args.pages_path:
		terms = entryTextFilter(terms, args.categories_path, args.pages_path, args.redirects_path, args.temps_cache_path, args.label_lang, args.exclude_labels, args.exclude_temps, args.verbose)

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for term in terms:
			print(term, file=out_file)

def catFilter(categories_path: str, include_cats: set[int], exclude_cats: set[int], return_titles: bool = False, max_depth: int = -1, verbose: bool = False) -> Union[set[int], set[str]]:
	if verbose:
		print('Reading the contents of all categories...')
	cat_members = collections.defaultdict(list)
	for cat_data in parseCats.catsGen(categories_path):
		cat_members[cat_data.catId].append((cat_data.pageId, cat_data.pageTitle))

	if verbose:
		print('Looking for pages and subcategories in specified categories:')
	# collect subcats to process in the next round
	next_include_cats = set()
	next_exclude_cats = set()
	ever_included_cats = include_cats.copy()
	ever_excluded_cats = exclude_cats.copy()
	# collect non-cat pages in cats
	include_pages = set()
	exclude_pages = set()

	depth = 0
	while (include_cats or exclude_cats) and (max_depth < 0 or depth <= max_depth):
		for cat_id in include_cats:
			for pageId, pageTitle in cat_members[cat_id]:
				if pageTitle.startswith(CAT_PREFIX):
					if pageId not in ever_included_cats:
						next_include_cats.add(pageId)
						ever_included_cats.add(pageId)
						if verbose:
							print(f'+ {pageTitle.removeprefix(CAT_PREFIX)}')
				# a page to include
				elif return_titles:
					include_pages.add(pageTitle)
				else:
					include_pages.add(pageId)
		for cat_id in exclude_cats:
			for pageId, pageTitle in cat_members[cat_id]:
				if pageTitle.startswith(CAT_PREFIX):
					if pageId not in ever_excluded_cats:
						next_exclude_cats.add(pageId)
						ever_excluded_cats.add(pageId)
						if verbose:
							print(f'- {pageTitle.removeprefix(CAT_PREFIX)}')
				# a page to exclude
				elif return_titles:
					exclude_pages.add(pageTitle)
				else:
					exclude_pages.add(pageId)
		include_cats = next_include_cats
		exclude_cats = next_exclude_cats
		next_include_cats = set()
		next_exclude_cats = set()
		depth += 1

	return include_pages - exclude_pages

def entryTextFilter(terms: set[str], categories_path: str, pages_path: str, redirects_path: str, temps_cache_path: Optional[str], label_lang: str, exclude_labels: set[str], exclude_temps: set[str], verbose: bool = False) -> set[str]:

	if verbose:
		print('Finding all form-of templates and their aliases...')
	if temps_cache_path:
		try:
			with open(temps_cache_path, encoding='utf-8') as temps_cache_file:
				form_of_temps = set(temps_cache_file.read().splitlines())
		except FileNotFoundError:
			form_of_temps = catFilter(categories_path, {FORM_OF_TEMP_CAT_ID}, set(), return_titles=True)
			with open(temps_cache_path, 'w', encoding='utf-8') as temps_cache_file:
				for temp in form_of_temps:
					print(temp, file=temps_cache_file)
	else:
		form_of_temps = catFilter(categories_path, {FORM_OF_TEMP_CAT_ID}, set(), return_titles=True)

	form_of_temps = {temp.removeprefix(TEMP_PREFIX) for temp in includeRedirects(form_of_temps, redirects_path)}
	exclude_temps = {temp.removeprefix(TEMP_PREFIX) for temp in includeRedirects({f'{TEMP_PREFIX}:{temp}' for temp in exclude_temps}, redirects_path)}
	sense_lines = findSenseLines(terms, pages_path, verbose)

	if verbose:
		print('Checking forms...')
	for term in sense_lines:
		if not checkTerm(term, sense_lines, form_of_temps, exclude_labels, exclude_temps):
			terms.remove(term)

	return terms

def findSenseLines(terms: set[str], pages_path: str, verbose: bool = False) -> dict[str, list[str]]:
	sense_lines = {}

	if verbose:
		print('\nLoading pages data:')
	for count, page in enumerate(pulldomHelpers.getPageDescendantText(pages_path, ['title', 'text'])):
		if page['title'] in terms:
			sense_lines[page['title']] = [line for line in page['text'].splitlines() if line.startswith('# ')]
		if verbose and count % PAGES_VERBOSITY_FACTOR == 0:
			print(count)
	return sense_lines

def checkTerm(term: str, sense_lines: dict[str, list[str]], form_of_temps: set[str], exclude_labels: set[str], exclude_temps: set[str], time_to_live: int = 4) -> bool:
	# if after following a few links we still haven't found a lemma, assume we are in a loop and accept the term
	if time_to_live <= 0:
		return True
	for line in sense_lines[term]:
		temps = wikitextparser.parse(line).templates
		try:
			form_of_temp = next(t for t in temps if t.normal_name() in form_of_temps)
			main_form = (form_of_temp.get_arg('2') or form_of_temp.get_arg('1')).value
			if main_form not in sense_lines or not checkTerm(main_form, sense_lines, form_of_temps, exclude_labels, exclude_temps, time_to_live - 1):
				continue
		except StopIteration:
			pass
		try:
			label_temp = next(t for t in temps if t.normal_name() in LABEL_TEMPS and t.arguments[0].positional and t.get_arg('1').value == 'en')
			labels = {a.value for a in label_temp.arguments[1:] if a.positional}
			if not labels.isdisjoint(exclude_labels):
				continue
		except StopIteration:
			pass
		if any(temp.normal_name() in exclude_temps for temp in temps):
			continue
		return True
	return False


def includeRedirects(pages: set[str], redirects_path: str) -> set[str]:
	# assumes no double redirects
	for red in parseRedirects.redirectsGen(redirects_path):
		if red.dstTitle in pages:
			pages.add(red.srcTitle)
	return pages

if __name__ == '__main__':
	main()
