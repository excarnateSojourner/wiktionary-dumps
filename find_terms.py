import argparse
import collections
from typing import Optional, Union
import xml.dom.pulldom

import wikitextparser

import parse_cats
import parse_redirects
import parse_stubs
import pulldom_helpers

PAGES_VERBOSITY_FACTOR = 10 ** 4
CAT_PREFIX = 'Category:'
TEMP_PREFIX = 'Template:'
# The ID of Category:Form-of templates
FORM_OF_TEMP_CAT_ID = 3991887
LABEL_TEMPS = {'label', 'lb', 'lbl'}

def main():
	parser = argparse.ArgumentParser('Find Terms')
	parser.add_argument('categories_path', help='Path of the parsed categories file that should be used to enumerate subcategories of explicitly mentioned categories.')
	parser.add_argument('output_path', help='Path of the file to write the IDs of pages in the categories to.')
	parser.add_argument('-i', '--include', required=True, nargs='+', default=[], help='Categories to include. These can either all be given as page titles, in which case --stubs-path is required to convert them to page ids, or they can all be given as page IDs (in which case --stubs-path must *not* be given).')
	parser.add_argument('-e', '--exclude', nargs='+', default=[], help='Categories to exclude (overriding includes).')
	parser.add_argument('-s', '--stubs-path', help='Path of the CSV file (as produced by parse_stubs.py) containing page IDs and titles. If given, this indicates that the categories to include and exclude have been specified using their IDs rather than their names. Specifying IDs removes the need for this program to perform time-intensive name-to-id translation.')
	parser.add_argument('-u', '--output-ids', action='store_true', help='Indicates that the output should be given as a list of IDs rather than a list of terms. Ignored if --pages-path is given (indicating that the text of entries should be processed as well).')
	parser.add_argument('-d', '--depth', default=-1, type=int, help='The maximum depth to explore each category\'s descendants. Zero means just immediate children, one means children and grandchildren, etc. A negative value means no limit.')
	parser.add_argument('-a', '--small-ram', action='store_true', help='Indicates that not enough memory (RAM) is available to read all category associations into memory, so they should instead be repeatedly read from disk, even though this is slower. Otherwise this program may use several gigabytes of RAM. (In 2024-01 I ran this with all category associations for the English Wiktionary and it used about 8 GB of RAM.)')
	parser.add_argument('-p', '--pages-path', help='Only intended for mainspace Wiktionary entries. If given, an additional layer of filtering is performed to remove forms of terms that are removed by analyzing their sense lines. This is useful because on Wiktionary forms (e.g. inflections and alternative forms) often lack the full categorization of their lemmas.')
	parser.add_argument('-r', '--redirects-path', help='The path of the CSV redirects file produced by parse_redirects.py. Ignored if --pages-path is not given.')
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

		for stub in parse_stubs.stubs_gen(args.stubs_path):
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

	if args.small_ram:
		terms = deep_cat_filter_slow(args.categories_path, include_cats, exclude_cats, return_titles=not args.output_ids or args.pages_path, max_depth=args.depth, verbose=args.verbose)
	else:
		terms = deep_cat_filter(args.categories_path, include_cats, exclude_cats, return_titles=not args.output_ids or args.pages_path, max_depth=args.depth, verbose=args.verbose)
	terms = list(terms)

	if args.pages_path:
		term_filter = TermFilter(args.pages_path, args.label_lang, args.categories_path, args.redirects_path, args.temps_cache_path, args.exclude_labels, args.exclude_temps, args.small_ram, args.verbose)
		if args.verbose:
			print('Checking the senses of each term...')
		terms = [term for term in terms if term_filter.check_term(term)]

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for term in terms:
			print(term, file=out_file)

def deep_cat_filter(categories_path: str, include_cats: set[int], exclude_cats: set[int], return_titles: bool = False, max_depth: int = -1, verbose: bool = False) -> Union[set[int], set[str]]:
	if verbose:
		print('Reading the contents of all categories...')
	cat_members = collections.defaultdict(list)
	for cat_data in parse_cats.cats_gen(categories_path):
		cat_members[cat_data.cat_id].append((cat_data.page_id, cat_data.page_title))

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
			for page_id, page_title in cat_members[cat_id]:
				if page_title.startswith(CAT_PREFIX):
					if page_id not in ever_included_cats:
						next_include_cats.add(page_id)
						ever_included_cats.add(page_id)
						if verbose:
							print(f'+ {page_title.removeprefix(CAT_PREFIX)}')
				# a page to include
				elif return_titles:
					include_pages.add(page_title)
				else:
					include_pages.add(page_id)
		for cat_id in exclude_cats:
			for page_id, page_title in cat_members[cat_id]:
				if page_title.startswith(CAT_PREFIX):
					if page_id not in ever_excluded_cats:
						next_exclude_cats.add(page_id)
						ever_excluded_cats.add(page_id)
						if verbose:
							print(f'- {page_title.removeprefix(CAT_PREFIX)}')
				# a page to exclude
				elif return_titles:
					exclude_pages.add(page_title)
				else:
					exclude_pages.add(page_id)
		include_cats = next_include_cats
		exclude_cats = next_exclude_cats
		next_include_cats = set()
		next_exclude_cats = set()
		depth += 1

	return include_pages - exclude_pages

def deep_cat_filter_slow(categories_path: str, include_cats: set[int], exclude_cats: set[int], return_titles: bool = False, max_depth: int = -1, verbose: bool = False) -> Union[set[int], set[str]]:
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
		if verbose:
			print('', '-' * 10, f'Round {depth}', '-' * 10, sep='\n')
		for data in parse_cats.cats_gen(categories_path):
			if data.cat_id in include_cats:
				if data.page_title.startswith(CAT_PREFIX):
					if data.page_id not in ever_included_cats:
						next_include_cats.add(data.page_id)
						ever_included_cats.add(data.page_id)
						if verbose:
							print(f'+ {data.page_title.removeprefix(CAT_PREFIX)}')
				# a page to include
				elif return_titles:
					include_pages.add(data.page_title)
				else:
					include_pages.add(data.page_id)
			if data.cat_id in exclude_cats:
				if data.page_title.startswith(CAT_PREFIX):
					if data.page_id not in ever_excluded_cats:
						next_exclude_cats.add(data.page_id)
						ever_excluded_cats.add(data.page_id)
						if verbose:
							print(f'+ {data.page_title.removeprefix(CAT_PREFIX)}')
				# a page to exclude
				elif return_titles:
					exclude_pages.add(data.page_title)
				else:
					exclude_pages.add(data.page_id)
		include_cats = next_include_cats
		exclude_cats = next_exclude_cats
		next_include_cats = set()
		next_exclude_cats = set()
		depth += 1

	return include_pages - exclude_pages

class TermFilter:
	def __init__(self,
			pages_path: str,
			label_lang: str,
			categories_path: Optional[str] = None,
			redirects_path: Optional[str] = None,
			temps_cache_path: Optional[str] = None,
			exclude_labels: Optional[set[str]] = None,
			exclude_temps: Optional[set[str]] = None,
			small_ram: bool = False,
			verbose: bool = False):
		if not (categories_path and redirects_path) and not temps_cache_path:
			raise ValueError('TermFilter requires either categories_path and redirect_path so that it can find all form-of templates, or temp_cache_path so that it can use a known list of form-of templates.')

		self.verbose = verbose
		self.sense_temps = self.find_sense_temps(pages_path)

		try:
			with open(temps_cache_path, encoding='utf-8') as temps_cache_file:
				self.form_of_temps = set(temps_cache_file.read().splitlines())
		# either temps_cache_path was not given or the file does not exist
		except (TypeError, FileNotFoundError):
			if verbose:
				print('Finding all form-of templates and their aliases:')
			self.form_of_temps = self.find_form_of_temps(categories_path, redirects_path, small_ram, verbose)
		try:
			with open(temps_cache_path, 'x', encoding='utf-8') as temps_cache_file:
				for temp in self.form_of_temps:
					print(temp, file=temps_cache_file)
		except FileExistsError:
			pass

		self.label_lang = label_lang
		self.exclude_labels = exclude_labels
		self.exclude_temps = {temp.removeprefix(TEMP_PREFIX) for temp in include_redirects({TEMP_PREFIX + temp for temp in exclude_temps}, redirects_path)}
		self.cache = {}

	def check_term(self, term: str, time_to_live: int = 4) -> bool:
		if term not in self.cache:
			self.cache[term] = self.check_uncached_term(term, time_to_live)
		return self.cache[term]

	def check_uncached_term(self, term: str, time_to_live: int = 4) -> bool:
		# if after following a few links we still haven't found a lemma, assume we are in a loop and accept the term
		if time_to_live <= 0:
			return True
		if term not in self.sense_temps:
			return False

		for temps in self.sense_temps[term]:
			if any(temp.normal_name() in self.exclude_temps for temp in temps):
				continue
			try:
				label_temp = next(temp for temp in temps if temp.normal_name() in LABEL_TEMPS and temp.arguments[0].positional and temp.get_arg('1').value == self.label_lang)
				if any((arg.value in self.exclude_labels) for arg in label_temp.arguments[1:] if arg.positional):
					continue
			except StopIteration:
				pass
			try:
				form_of_temp = next(temp for temp in temps if temp.normal_name() in self.form_of_temps)
				main_form = (form_of_temp.get_arg('2') or form_of_temp.get_arg('1')).value
				if not self.check_term(main_form, time_to_live - 1):
					continue
			except StopIteration:
				pass
			return True
		return False

	def find_sense_temps(self, pages_path: str) -> dict[str, list[wikitextparser._template.Template]]:
		sense_temps = {}

		if self.verbose:
			print('\nLoading pages data:')
		for count, page in enumerate(pulldom_helpers.get_page_descendant_text(pages_path, ['title', 'text'])):
			sense_temps[page['title']] = [wikitextparser.parse(line).templates for line in page['text'].splitlines() if line.startswith('# ')]
			if self.verbose and count % PAGES_VERBOSITY_FACTOR == 0:
				print(count)
		return sense_temps

	def find_form_of_temps(self, categories_path: str, redirects_path: str, small_ram: bool = False, verbose: bool = False):
		if small_ram:
			form_of_temps = deep_cat_filter_slow(categories_path, {FORM_OF_TEMP_CAT_ID}, set(), return_titles=True, verbose=verbose)
		else:
			form_of_temps = deep_cat_filter(categories_path, {FORM_OF_TEMP_CAT_ID}, set(), return_titles=True, verbose=verbose)

		return {temp.removeprefix(TEMP_PREFIX) for temp in include_redirects(form_of_temps, redirects_path)}

# end of TermFilter

def include_redirects(pages: set[str], redirects_path: str) -> set[str]:
	# assumes no double redirects
	for red in parse_redirects.redirects_gen(redirects_path):
		if red.dst_title in pages:
			pages.add(red.src_title)
	return pages

if __name__ == '__main__':
	main()
