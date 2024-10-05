import argparse
import collections.abc
import json
import os.path
import re

import wikitextparser

import deep_cat
import etree_helpers
import parse_cats
import parse_redirects
import parse_stubs

PAGES_VERBOSITY_FACTOR = 10 ** 4
TEMP_PREFIX = 'Template:'
# The ID of Category:Form-of templates
FORM_OF_TEMP_CAT_ID = 3991887
LABEL_TEMPS = {'label', 'lb', 'lbl'}

def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument('-c', '--config-path', help='The path of a JSON file containing arguments and options to use. All argument and option names are the same as the command-line ones, but spaces may be used in place of underscores and dashes. Command-line arguments can be used in addition to a config to override arguments and options in the config.')
	parser.add_argument('-s', '--stubs-path', help='[required] The path of the CSV stubs file (as produced by parse_stubs.py) containing page IDs and titles.')
	parser.add_argument('-r', '--redirects-path', help='[required] The path of the CSV redirects file produced by parse_redirects.py.')
	parser.add_argument('-p', '--pages-path', help='[required] The path of the pages file containing the page text of all terms in the included categories. Page text is used to follow form-of template links to the lemma (main form) of a term, which is likely categorized more completely than e.g. a plural or past tense verb.')
	parser.add_argument('-o', '--output-path', help='[required] The path of the file to write the IDs of selected terms to.')
	# g is the first untaken letter in 'starting terms'
	parser.add_argument('-g', '--initial-terms-path', help='The path of a text file containing an initial list of terms to start with, one term per line. Required if --cats-path and --include-cats are not given.')
	parser.add_argument('-a', '--cats-path', help='The path of the CSV categories file (as produced by parse_cats.py) that should be used to find subcategories of explicitly mentioned categories. Required if --initial-terms-path is not given. Ignored if neither --include-cats nor --exclude-cats is given.')
	parser.add_argument('-i', '--include-cats', nargs='+', help='[required] Categories from which to collect selected terms. At least one category must be given to generate the initial list of terms. These can either all be given as page titles, in which case --stubs-path is required to convert them to page IDs, or they can all be given as page IDs (in which case --stubs-path must *not* be given). If you want to include all terms in a language, you can do this by including the categories "[Language name] lemmas" and "[Language name] non-lemma forms". Required if --initial-terms-path is not given. Requires --cats-path.')
	parser.add_argument('-e', '--exclude-cats', nargs='+', default=[], help='Terms in these categories (and their subcategories) will be excluded (overriding included categories). Requires --cats-path.')
	parser.add_argument('-d', '--depth', default=-1, type=int, help='The maximum depth to explore each category\'s descendants. By default there is no limit (indicated by a negative value). Zero means just immediate children, one means children and grandchildren, and so on. Ignored if neither --include-cats nor --exclude-cats is given.')
	# m for memory
	parser.add_argument('-m', '--small-ram', action='store_true', help='Indicates that not enough memory (RAM) is available to read all category associations into memory, so they should instead be repeatedly read from disk, even though this is slower. Otherwise this program may use several gigabytes of RAM. (In 2024-01 I ran this with all category associations for the English Wiktionary and it used about 8 GB of RAM.) Ignored if neither --include-cats nor --exclude-cats is given.')
	parser.add_argument('-x', '--regex', help='A regular expression that terms must fully match to be included. Matching is performed by Python\'s re.fullmatch(), so see that module\'s documentation for details. Note that the entire term must "fit within" the given regex, so if you want to find terms that merely *contain* a particular pattern, add .* at the beginning and end of your regex.')
	parser.add_argument('-l', '--label-lang', default='en', help='The Wiktionary language code (usually the ISO 639 code) of the language for which to exclude labels. Defaults to "en" for English. Ignored if --exclude-labels is not also given.')
	# b is the second letter in the commonly used alias {{lb}}
	parser.add_argument('-b', '--exclude-labels', nargs='+', default=[], help='If a sense of a term has one of these labels, that sense will not support the inclusion of the term. (The term may still be included if it has other "valid" senses.) Labels are positional arguments of the {{label}} (AKA {{lb}}) template (excluding the language code). Requires --label-lang.')
	parser.add_argument('-t', '--exclude-temps', nargs='+', default=[], help='If a given template given here is used in a sense of a term, that sense will not support the inclusion of the term. (The term may still be included if it has other "valid" senses.)')
	# f for form-of
	parser.add_argument('-f', '--temps-cache-path', help='The path of a file in which to cache (and later retrieve) a list of templates required for form-of filtering. If you want to entirely avoid following form-of links in entries, use this option with the path of an empty file.')
	# n for noun
	parser.add_argument('-n', '--parts-of-speech', nargs='+', default=[], help='If a sense is not one of these parts of speech (think noun, verb, etc) then it will not support the inclusion of a term. Case insensitive.')
	# u is the first untaken letter in 'output ids'
	parser.add_argument('-u', '--output-ids', action='store_true', help='Output the MediaWiki IDs of the selected entries rather than the titles of the entries.')
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

	required = ['stubs-path', 'redirects-path', 'pages-path', 'output_path']
	for arg in required:
		if not getattr(config, arg.replace('-', '_')):
			raise ValueError(f'Missing required argument --{arg}')

	# For each of these tuples at least of one of its arguments must be given
	one_required = [
		('initial-terms-path', 'include-cats'),
		('temps-cache-path', 'cats-path')
	]
	for options in one_required:
		if not any(getattr(config, opt.replace('-', '_')) for opt in options):
			raise ValueError('At least one of the following must be given: ' + ', '.join(f'--{opt}' for opt in options))

	# Each key requires that its value also be given
	dependencies = {
		'include-cats': 'cats-path',
		'exclude-cats': 'cats-path',
		'exclude-labels': 'label-lang'
	}
	for used, required in dependencies.items():
		if getattr(config, used.replace('-', '_')) and not getattr(config, required.replace('-', '_')):
			raise ValueError(f'--{used} requires --{required}')

	if config.verbose:
		print(f'Reading stubs...')
	stub_master = parse_stubs.StubMaster(config.stubs_path)

	if not config.small_ram:
		cat_master = parse_cats.CategoryMaster(config.cats_path, verbose=config.verbose)

	good_terms = []
	if config.initial_terms_path:
		with open(config.initial_terms_path, encoding='utf-8') as initial_terms_file:
			for line in initial_terms_file:
				good_terms.append(stub_master.id(line[:-1]))

	if config.include_cats:
		include_cats = {stub_master.id(parse_cats.CAT_NAMESPACE_PREFIX + cat) for cat in config.include_cats}
		if config.small_ram:
			good_terms.extend(deep_cat.deep_cat_filter_slow(config.cats_path, include_cats, return_titles=False, max_depth=config.depth, verbose=config.verbose))
		else:
			good_terms.extend(deep_cat.deep_cat_filter(cat_master, include_cats, return_titles=False, max_depth=config.depth, verbose=config.verbose))
	if config.exclude_cats:
		exclude_cats = {stub_master.id(parse_cats.CAT_NAMESPACE_PREFIX + cat) for cat in config.exclude_cats}
		if config.small_ram:
			cat_bad_terms = deep_cat.deep_cat_filter_slow(config.cats_path, exclude_cats, return_titles=False, max_depth=config.depth, verbose=config.verbose)
		else:
			cat_bad_terms = deep_cat.deep_cat_filter(cat_master, exclude_cats, return_titles=False, max_depth=config.depth, verbose=config.verbose)
	else:
		cat_bad_terms = set()

	form_of_temps = None
	if config.temps_cache_path:
		# Attempt to read form-of templates
		try:
			with open(config.temps_cache_path, encoding='utf-8') as temps_cache_file:
				form_of_temps = set(temps_cache_file.read().splitlines())
		except FileNotFoundError:
			pass
	if not form_of_temps:
		if verbose:
			print('Finding all form-of templates and their aliases:')
		if config.small_ram:
			form_of_temps = deep_cat.deep_cat_filter_slow(cats_path, {FORM_OF_TEMP_CAT_ID}, return_titles=True, verbose=verbose)
		else:
			form_of_temps = deep_cat.deep_cat_filter(cat_master, {FORM_OF_TEMP_CAT_ID}, return_titles=True, verbose=verbose)
	form_of_temps = {temp.removeprefix(TEMP_PREFIX) for temp in include_redirects(form_of_temps, config.redirects_path)}
	# Attempt to cache form-of templates
	try:
		with open(config.temps_cache_path, 'x', encoding='utf-8') as temps_cache_file:
			for temp in form_of_temps:
				print(temp, file=temps_cache_file)
	except FileExistsError:
		pass

	if not config.small_ram:
		del cat_master

	term_filter = TermFilter(
		config.pages_path,
		config.label_lang,
		config.redirects_path,
		form_of_temps=form_of_temps,
		bad_terms=cat_bad_terms,
		regex=config.regex,
		exclude_labels=set(config.exclude_labels),
		exclude_temps=config.exclude_temps,
		parts_of_speech=set(config.parts_of_speech),
		verbose=config.verbose
	)

	if config.verbose:
		print('Checking the senses of each term...')
	good_terms = [entry_id for entry_id in good_terms if term_filter.check_entry(entry_id)]

	if not config.output_ids:
		good_terms = [stub_master.title(entry_id) for entry_id in good_terms]

	with open(config.output_path, 'w', encoding='utf-8') as out_file:
		for term in good_terms:
			print(term, file=out_file)

class TermFilter:
	def __init__(self,
			pages_path: str,
			label_lang: str,
			redirects_path: str,
			form_of_temps: set[str] | None = None,
			bad_terms: collections.abc.Collection[int] | None = None,
			regex: str = '',
			exclude_labels: collections.abc.Container[str] | None = None,
			exclude_temps: collections.abc.Iterable[str] | None = None,
			parts_of_speech: collections.abc.Container[str] | None = None,
			verbose: bool = False):

		# Set verbose first so it can be used by find_sense_temps
		self.verbose = verbose
		self.sense_temps = self.find_sense_temps(pages_path, bad_terms, regex, parts_of_speech)
		self.label_lang = label_lang
		self.form_of_temps = form_of_temps or set()
		self.exclude_labels = exclude_labels
		self.exclude_temps = {temp.removeprefix(TEMP_PREFIX) for temp in include_redirects({TEMP_PREFIX + temp for temp in exclude_temps}, redirects_path)}
		self.cache = {id_: False for id_ in bad_terms} if bad_terms else {}

	def check_entry(self, term_id: int, time_to_live: int = 4) -> bool:
		if term_id not in self.cache:
			self.cache[term_id] = self.check_uncached_term(term_id, time_to_live)
		return self.cache[term_id]

	def check_uncached_term(self, term_id: int, time_to_live: int = 4) -> bool:
		# If after following a few links we still haven't found a lemma, assume we are in a cycle and accept the term
		if time_to_live <= 0:
			return True
		if term_id not in self.sense_temps:
			return False

		for temps in self.sense_temps[term_id]:
			if any(temp.normal_name() in self.exclude_temps for temp in temps):
				continue
			try:
				label_temp = next(temp for temp in temps if temp.normal_name() in LABEL_TEMPS and temp.get_arg('1').positional and temp.get_arg('1').value == self.label_lang)
				if any((arg.value in self.exclude_labels) for arg in label_temp.arguments[1:] if arg.positional):
					continue
			except StopIteration:
				pass
			try:
				form_of_temp = next(temp for temp in temps if temp.normal_name() in self.form_of_temps)
				main_form = (form_of_temp.get_arg('2') or form_of_temp.get_arg('1')).value
				if not self.check_entry(main_form, time_to_live - 1):
					continue
			except StopIteration:
				pass
			return True
		return False

	def find_sense_temps(self,
			pages_path: str,
			bad_terms: collections.abc.Collection[int] | None = None,
			regex: str | None = None,
			parts_of_speech: collections.abc.Container[str] | None = None
			) -> dict[str, list[list[wikitextparser.Template]]]:

		def temps_in_section(section: str) -> list[list[wikitextparser.Template]]:
			return [wikitextparser.parse(line).templates for line in section.splitlines() if line.startswith('# ')]

		sense_temps = collections.defaultdict(list)
		if self.verbose:
			print('\nLoading pages data:')

		for count, page in enumerate(etree_helpers.pages_gen(pages_path)):
			page_id = int(etree_helpers.find_child(page, 'id').text)
			page_title = etree_helpers.find_child(page, 'title').text
			page_text = etree_helpers.find_child(etree_helpers.find_child(page, 'revision'), 'text').text
			if not (bad_terms and page_id in bad_terms) and not (regex and not re.fullmatch(regex, page_title)):
				if parts_of_speech:
					# Assume lang has removed all L2 sections except for the relevant one
					wikitext = wikitextparser.parse(page_text).get_sections(level=2)[0]
					for section in wikitext.get_sections(level=3):
						# Multiple etymologies
						if re.fullmatch(r'Etymology \d+', section.title):
							for subsection in section.get_sections(level=4):
								if subsection.title.casefold() in parts_of_speech:
									sense_temps[page_id].extend(temps_in_section(subsection.contents))
						# Single etymology
						else:
							if section.title.casefold() in parts_of_speech:
								sense_temps[page_id].extend(temps_in_section(section.contents))
					page.clear()

				# No parts of speech specified
				else:
					sense_temps[page_id] = temps_in_section(page_text)

			page.clear()
			if self.verbose and count % PAGES_VERBOSITY_FACTOR == 0:
				print(f'{count:,}')

		return sense_temps

# End of TermFilter

def include_redirects(pages: set[str], redirects_path: str) -> set[str]:
	# Assumes no double redirects
	for red in parse_redirects.redirects_gen(redirects_path):
		if red.dst_title in pages:
			pages.add(red.src_title)
	return pages

if __name__ == '__main__':
	main()
