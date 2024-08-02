import argparse
import collections.abc
import functools
import json
import os.path
import re

import wikitextparser

import deep_cat
import etree_helpers
import parse_cats
import parse_redirects

PAGES_VERBOSITY_FACTOR = 10 ** 4
TEMP_PREFIX = 'Template:'
# The ID of Category:Form-of templates
FORM_OF_TEMP_CAT_ID = 3991887
LABEL_TEMPS = {'label', 'lb', 'lbl'}

def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument('-c', '--config-path', help='The path of a JSON file containing arguments and options to use. All argument and option names are the same as the command-line ones, but spaces may be used in place of underscores and dashes. Command-line arguments can be used in addition to a config to override arguments and options in the config.')
	parser.add_argument('-p', '--pages-path', help='The path of the pages file containing the page text of all terms in the included categories. Page text is used to follow form-of template links to the lemma (main form) of a term, which is likely categorized more completely than e.g. a plural or past tense verb.')
	parser.add_argument('-a', '--cats-path', help='The path of the CSV categories file (as produced by parse_cats.py) that should be used to find subcategories of explicitly mentioned categories.')
	parser.add_argument('-r', '--redirects-path', help='The path of the CSV redirects file produced by parse_redirects.py.')
	parser.add_argument('-o', '--output-path', help='The path of the file to write the IDs of selected terms to.')
	parser.add_argument('-i', '--include-cats', nargs='+', help='Categories from which to collect selected terms. At least one category must be given to generate the initial list of terms. These can either all be given as page titles, in which case --stubs-path is required to convert them to page IDs, or they can all be given as page IDs (in which case --stubs-path must *not* be given). If you want to include all terms in a language, you can do this by including the categories "[Language name] lemmas" and "[Language name] non-lemma forms".')
	parser.add_argument('-e', '--exclude-cats', nargs='+', default=[], help='Terms in these categories will be excluded (overriding included categories).')
	parser.add_argument('-s', '--stubs-path', help='The path of the CSV stubs file (as produced by parse_stubs.py) containing page IDs and titles. If given, this indicates that the categories to select have been specified using their titles rather than their IDs (and vice-versa).')
	parser.add_argument('-d', '--depth', default=-1, type=int, help='The maximum depth to explore each category\'s descendants. By default there is no limit (indicated by a negative value). Zero means just immediate children, one means children and grandchildren, and so on.')
	# m for memory
	parser.add_argument('-m', '--small-ram', action='store_true', help='Indicates that not enough memory (RAM) is available to read all category associations into memory, so they should instead be repeatedly read from disk, even though this is slower. Otherwise this program may use several gigabytes of RAM. (In 2024-01 I ran this with all category associations for the English Wiktionary and it used about 8 GB of RAM.)')
	parser.add_argument('-x', '--regex', help='A regular expression that terms must fully match to be included. Matching is performed by Python\'s re.fullmatch(), so see that module\'s documentation for details. Note that the entire term must "fit within" the given regex, so if you want to find terms that merely *contain* a particular pattern, add .* at the beginning and end of your regex.')
	parser.add_argument('-l', '--label-lang', default='en', help='The Wiktionary language code (usually the ISO 639 code) of the language for which to exclude labels. Defaults to "en" for English. Ignored if --exclude-labels is not also given.')
	# b is the second letter in the commonly used alias {{lb}}
	parser.add_argument('-b', '--exclude-labels', nargs='+', default=[], help='If a sense of a term has one of these labels, that sense will not support the inclusion of the term. (The term may still be included if it has other "valid" senses.) Labels are positional arguments of the {{label}} (AKA {{lb}}) template (excluding the language code). Requires --label-lang.')
	parser.add_argument('-t', '--exclude-temps', nargs='+', default=[], help='If a given template given here is used in a sense of a term, that sense will not support the inclusion of the term. (The term may still be included if it has other "valid" senses.)')
	# f for form-of
	parser.add_argument('-f', '--temps-cache-path', help='The path of a file in which to cache (and later retrieve) a list of templates required for form-of filtering. If you want to entirely avoid following form-of links in entries, use this option with the path of an empty file.')
	# n for noun
	parser.add_argument('-n', '--parts-of-speech', nargs='+', default=[], help='If a sense is not one of these parts of speech (think noun, verb, etc) then it will not support the inclusion of a term. Case insensitive.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()
	if args.config_path:
		with open(args.config_path, encoding='utf-8') as config_file:
			config_file_values = json.load(config_file)
		parser.set_defaults(**{k.replace(' ', '_').replace('-', '_'): v for k, v in config_file_values.items()})
		# Reparse with config file values as defaults
		config = parser.parse_args()
	else:
		config = args
	if not all([config.pages_path, config.cats_path, config.redirects_path, config.output_path]):
		raise ValueError('Missing at least one of --pages-path, --cats-path, --redirects-path, --output-path, and --include-cats.')

	if config.stubs_path:
		# cats are initially stored in lists to preserve order for printing
		include_cats = deep_cat.cat_titles_to_ids(config.include_cats, config.stubs_path)
		exclude_cats = deep_cat.cat_titles_to_ids(config.exclude_cats, config.stubs_path)
		if config.verbose:
			print(f'If you want to use the same sets of included and excluded categories again later, you can use the following command line arguments (omitting --stubs-path) to provide the IDs of the categories (to save the time of converting from titles to IDs):')
			print(f'-i {" ".join(str(cat) for cat in include_cats)} -e {" ".join(str(cat) for cat in exclude_cats)}')
		# order isn't important now, so convert to sets to prepare for deep_cat_filter
		include_cats = set(include_cats)
		exclude_cats = set(exclude_cats)
	else:
		include_cats = set(int(cat) for cat in config.include_cats)
		exclude_cats = set(int(cat) for cat in config.exclude_cats)

	if config.small_ram:
		good_terms = deep_cat.deep_cat_filter_slow(config.cats_path, include_cats, return_titles=True, max_depth=config.depth, verbose=config.verbose)
		cat_bad_terms = deep_cat.deep_cat_filter_slow(config.cats_path, exclude_cats, return_titles=True, max_depth=config.depth, verbose=config.verbose)
	else:
		cat_master = parse_cats.CategoryMaster(config.cats_path, verbose=config.verbose)
		good_terms = deep_cat.deep_cat_filter(cat_master, include_cats, return_titles=True, max_depth=config.depth, verbose=config.verbose)
		cat_bad_terms = deep_cat.deep_cat_filter(cat_master, exclude_cats, return_titles=True, max_depth=config.depth, verbose=config.verbose)

	if config.regex:
		good_terms = [term for term in good_terms if re.fullmatch(config.regex, term)]

	term_filter_model = functools.partial(TermFilter, config.pages_path, config.label_lang, config.redirects_path, bad_terms=cat_bad_terms, temps_cache_path=config.temps_cache_path, exclude_labels=set(config.exclude_labels), exclude_temps=config.exclude_temps, parts_of_speech=set(p.casefold() for p in config.parts_of_speech), verbose=config.verbose)
	if config.small_ram:
		term_filter = term_filter_model(cats_path=config.cats_path)
	# If we have a known list of form-of temps, TermFilter doesn't need category data
	elif config.temps_cache_path and os.path.isfile(config.temps_cache_path):
		del cat_master
		term_filter = term_filter_model()
	else:
		term_filter = term_filter_model(cat_master=cat_master)
	if config.verbose:
		print('Checking the senses of each term...')
	good_terms = [term for term in good_terms if term_filter.check_term(term)]

	with open(config.output_path, 'w', encoding='utf-8') as out_file:
		for term in good_terms:
			print(term, file=out_file)

class TermFilter:
	def __init__(self,
			pages_path: str,
			label_lang: str,
			redirects_path: str,
			bad_terms: collections.abc.Collection[str] | None = None,
			cat_master: parse_cats.CategoryMaster | None = None,
			cats_path: str | None = None,
			temps_cache_path: str | None = None,
			exclude_labels: collections.abc.Container[str] | None = None,
			exclude_temps: collections.abc.Iterable[str] | None = None,
			parts_of_speech: collections.abc.Container[str] | None = None,
			verbose: bool = False):
		if not ((cat_master or cats_path) and redirects_path) and not temps_cache_path:
			raise ValueError('TermFilter requires either cats_path and redirects_path so that it can find all form-of templates, or temp_cache_path so that it can use a known list of form-of templates.')

		self.verbose = verbose
		self.sense_temps = self.find_sense_temps(pages_path, bad_terms, parts_of_speech)

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
		self.cache = {term: False for term in bad_terms} if bad_terms else {}

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

	def find_sense_temps(self,
			pages_path: str,
			bad_terms: collections.abc.Collection[str] | None = None,
			parts_of_speech: collections.abc.Container[str] | None = None
			) -> dict[str, list[list[wikitextparser.Template]]]:
		sense_temps = {}

		def temps_in_section(section: str) -> list[list[wikitextparser.Template]]:
			return [wikitextparser.parse(line).templates for line in section.splitlines() if line.startswith('# ')]

		if self.verbose:
			print('\nLoading pages data:')
		if parts_of_speech:
			for count, page in enumerate(etree_helpers.pages_gen(pages_path)):
				page_title = etree_helpers.find_child(page, 'title').text
				page_text = etree_helpers.find_child(etree_helpers.find_child(page, 'revision'), 'text').text
				if bad_terms and page_title in bad_terms:
					continue
				# Assume lang has removed all L2 sections except for the relevant one
				wikitext = wikitextparser.parse(page_text).get_sections(level=2)[0]
				for section in wikitext.get_sections(level=3):
					# Multiple etymologies
					if re.fullmatch(r'Etymology \d+', section.title):
						for subsection in section.get_sections(level=4):
							if subsection.title.casefold() in parts_of_speech:
								sense_temps[page_title] = temps_in_section(subsection.contents)
					# Single etymology
					else:
						if section.title.casefold() in parts_of_speech:
							sense_temps[page_title] = temps_in_section(section.contents)
				page.clear()

				if self.verbose and count % PAGES_VERBOSITY_FACTOR == 0:
					print(f'{count:,}')

		# No parts of speech specified
		else:
			for count, page in enumerate(etree_helpers.pages_gen(pages_path)):
				page_title = etree_helpers.find_child(page, 'title').text
				page_text = etree_helpers.find_child(etree_helpers.find_child(page, 'revision'), 'text').text
				if not (bad_terms and page_title in bad_terms):
					sense_temps[page_title] = temps_in_section(page_text)
				page.clear()

				if self.verbose and count % PAGES_VERBOSITY_FACTOR == 0:
					print(f'{count:,}')
		return sense_temps

	@classmethod
	def find_form_of_temps(cls,
			redirects_path: str,
			cat_master: parse_cats.CategoryMaster | None = None,
			cats_path: str | None = None,
			verbose: bool = False
			) -> set[str]:
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
