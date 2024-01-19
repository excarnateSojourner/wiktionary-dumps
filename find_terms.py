import argparse
import collections
import re
from typing import Optional
import xml.dom.pulldom

import wikitextparser

import deep_cat
import parse_cats
import parse_redirects
import pulldom_helpers

PAGES_VERBOSITY_FACTOR = 10 ** 4
TEMP_PREFIX = 'Template:'
# The ID of Category:Form-of templates
FORM_OF_TEMP_CAT_ID = 3991887
LABEL_TEMPS = {'label', 'lb', 'lbl'}

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path', help='The path of the pages file containing the page text of all terms in the included categories. Page text is used to follow form-of template links to the lemma (main form) of a term, which is likely categorized more completely than e.g. a plural or past tense verb.')
	parser.add_argument('cats_path', help='The path of the CSV categories file (as produced by parse_cats.py) that should be used to find subcategories of explicitly mentioned categories.')
	parser.add_argument('redirects_path', help='The path of the CSV redirects file produced by parse_redirects.py.')
	parser.add_argument('output_path', help='The path of the file to write the IDs of selected terms to.')
	parser.add_argument('-i', '--include-cats', required=True, nargs='+', help='Categories from which to collect selected terms. At least one category must be given to generate the initial list of terms. These can either all be given as page titles, in which case --stubs-path is required to convert them to page ids, or they can all be given as page IDs (in which case --stubs-path must *not* be given). If you want to include all terms in a language, you can do this by including "[Language] lemmas" and "[Language] non-lemma forms".')
	parser.add_argument('-e', '--exclude-cats', nargs='+', default=[], help='Terms in these categories will be excluded (overriding included categories).')
	parser.add_argument('-s', '--stubs-path', help='The path of the CSV stubs file (as produced by parse_stubs.py) containing page IDs and titles. If given, this indicates that the categories to select have been specified using their IDs rather than their names. Specifying IDs removes the need for this program to perform time-intensive name-to-id translation.')
	parser.add_argument('-d', '--depth', default=-1, type=int, help='The maximum depth to explore each category\'s descendants. By default there is no limit (indicated by a negative value). Zero means just immediate children, one means children and grandchildren, and so on.')
	parser.add_argument('-a', '--small-ram', action='store_true', help='Indicates that not enough memory (RAM) is available to read all category associations into memory, so they should instead be repeatedly read from disk, even though this is slower. Otherwise this program may use several gigabytes of RAM. (In 2024-01 I ran this with all category associations for the English Wiktionary and it used about 8 GB of RAM.)')
	parser.add_argument('-w', '--only-words', action='store_true', help='Indicates that multiword terms (terms spelled with spaces, hyphens, etc.) should be excluded.')
	parser.add_argument('-t', '--temps-cache-path', help='The path of a file in which to cache (and later retrieve) a list of templates required for form-of filtering. If you want to entirely avoid following form-of links in entries, use this option with the path of an empty file.')
	parser.add_argument('-l', '--label-lang', default='en', help='The Wiktionary language code (usually the ISO 639 code) of the language for which to exclude labels. Defaults to "en" for English. Ignored if --exclude-labels is not also given.')
	parser.add_argument('-x', '--exclude-labels', nargs='+', default=[], help='If a sense of a term has one of these labels, that sense will not support the inclusion of the term. (The term may still be included if it has other "valid" senses.) Labels are positional arguments of the {{label}} (AKA {{lb}}) template (excluding the language code). Requires --label-lang.')
	parser.add_argument('-m', '--exclude-temps', nargs='+', default=[], help='If a given template given here is used in a sense of a term, that sense will not support the inclusion of the term. (The term may still be included if it has other "valid" senses.)')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.stubs_path:
		# cats are initially stored in lists to preserve order for printing
		include_cats = deep_cat.cat_titles_to_ids(args.include_cats, args.stubs_path)
		exclude_cats = deep_cat.cat_titles_to_ids(args.exclude_cats, args.stubs_path)
		if args.verbose:
			print(f'If you want to use the same sets of included and excluded categories again later, you can use the following command line arguments (omitting --stubs-path) to provide the IDs of the categories (to save the time of converting from titles to IDs):')
			print(f'-i {" ".join(str(cat) for cat in include_cats)} -e {" ".join(str(cat) for cat in exclude_cats)}')
		# order isn't important now, so convert to sets to prepare for deep_cat_filter
		include_cats = set(include_cats)
		exclude_cats = set(exclude_cats)
	else:
		include_cats = set(int(cat) for cat in args.include_cats)
		exclude_cats = set(int(cat) for cat in args.exclude_cats)

	if args.small_ram:
		good_terms = deep_cat.deep_cat_filter_slow(args.cats_path, include_cats, return_titles=True, max_depth=args.depth, verbose=args.verbose)
		cat_bad_terms = deep_cat.deep_cat_filter_slow(args.cats_path, exclude_cats, return_titles=True, max_depth=args.depth, verbose=args.verbose)
	else:
		cat_master = parse_cats.CategoryMaster(args.cats_path, verbose=args.verbose)
		good_terms = deep_cat.deep_cat_filter(cat_master, include_cats, return_titles=True, max_depth=args.depth, verbose=args.verbose)
		cat_bad_terms = deep_cat.deep_cat_filter(cat_master, exclude_cats, return_titles=True, max_depth=args.depth, verbose=args.verbose)

	if args.only_words:
		good_terms = [term for term in good_terms if re.fullmatch(r'\w+', term)]

	if args.small_ram:
		term_filter = TermFilter(args.pages_path, args.label_lang, args.redirects_path, bad_terms=cat_bad_terms, cats_path=args.cats_path, temps_cache_path=args.temps_cache_path, exclude_labels=args.exclude_labels, exclude_temps=args.exclude_temps, verbose=args.verbose)
	else:
		term_filter = TermFilter(args.pages_path, args.label_lang, args.redirects_path, bad_terms=cat_bad_terms, cat_master=cat_master, temps_cache_path=args.temps_cache_path, exclude_labels=args.exclude_labels, exclude_temps=args.exclude_temps, verbose=args.verbose)
	if args.verbose:
		print('Checking the senses of each term...')
	good_terms = [term for term in good_terms if term_filter.check_term(term)]

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for term in good_terms:
			print(term, file=out_file)

class TermFilter:
	def __init__(self,
			pages_path: str,
			label_lang: str,
			redirects_path: str,
			bad_terms: Optional[collections.abc.Iterable[str]] = None,
			cat_master: Optional[parse_cats.CategoryMaster] = None,
			cats_path: Optional[str] = None,
			temps_cache_path: Optional[str] = None,
			exclude_labels: Optional[set[str]] = None,
			exclude_temps: Optional[set[str]] = None,
			verbose: bool = False):
		if not (cat_master or cats_path) and not temps_cache_path:
			raise ValueError('TermFilter requires either cats_path and redirects_path so that it can find all form-of templates, or temp_cache_path so that it can use a known list of form-of templates.')

		self.verbose = verbose
		self.sense_temps = self.find_sense_temps(pages_path)

		try:
			with open(temps_cache_path, encoding='utf-8') as temps_cache_file:
				self.form_of_temps = set(temps_cache_file.read().splitlines())
		# either temps_cache_path was not given or the file does not exist
		except (TypeError, FileNotFoundError):
			if verbose:
				print('Finding all form-of templates and their aliases:')
			if cat_master:
				self.form_of_temps = self.find_form_of_temps(redirects_path, cat_master=cat_master, verbose=verbose)
			else:
				self.form_of_temps = self.find_form_of_temps(redirects_path, cats_path=cats_path, verbose=verbose)
		try:
			with open(temps_cache_path, 'x', encoding='utf-8') as temps_cache_file:
				for temp in self.form_of_temps:
					print(temp, file=temps_cache_file)
		except (TypeError, FileExistsError):
			pass

		self.label_lang = label_lang
		self.exclude_labels = exclude_labels
		self.exclude_temps = {temp.removeprefix(TEMP_PREFIX) for temp in include_redirects({TEMP_PREFIX + temp for temp in exclude_temps}, redirects_path)}
		self.cache = {term: False for term in bad_terms}

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
				print(f'{count:,}')
		return sense_temps

	@classmethod
	def find_form_of_temps(cls, redirects_path: str, cat_master: Optional[parse_cats.CategoryMaster] = None, cats_path: Optional[str] = None, verbose: bool = False):
		if not cat_master and not cats_path:
			raise ValueError('TermFilter.find_form_of_temps() requires at least one of cat_master (parse_cats.CategoryMaster) and cats_path (str).')

		if cat_master:
			form_of_temps = deep_cat.deep_cat_filter(cat_master, {FORM_OF_TEMP_CAT_ID}, return_titles=True, verbose=verbose)
		else:
			form_of_temps = deep_cat.deep_cat_filter_slow(cats_path, {FORM_OF_TEMP_CAT_ID}, return_titles=True, verbose=verbose)

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
