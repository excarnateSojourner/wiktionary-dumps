import argparse
import collections.abc
import json
import os.path
import re

import wikitextparser
import wordfreq

import deep_cat
import parsing.etree_helpers
import parsing.parse_cats
import parsing.parse_redirects
import parsing.parse_stubs
import parsing.parse_temps

PAGES_VERBOSITY_FACTOR = 10 ** 5
CHECK_VERBOSITY_FACTOR = 10 ** 4
TEMP_PREFIX = 'Template:'
# The ID of Category:Form-of templates
FORM_OF_TEMP_CAT_ID = 3991887
LABEL_TEMPS = {'label', 'lb', 'lbl'}
WORD_FREQ_FACTOR = 10 ** 8

def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument('-c', '--config-path', help='The path of a JSON file containing arguments and options to use. All argument and option names are the same as the command-line ones, but spaces may be used in place of underscores and dashes. Command-line arguments can be used in addition to a config to override arguments and options in the config.')
	parser.add_argument('-s', '--stubs-path', help='[required] The path of the CSV stubs file (as produced by parse_stubs.py) containing page IDs and titles.')
	parser.add_argument('-r', '--redirects-path', help='[required] The path of the CSV redirects file produced by parse_redirects.py.')
	parser.add_argument('-p', '--pages-path', help='[required] The path of the pages file containing the page text of all terms in the included categories. Page text is used to follow form-of template links to the lemma (main form) of a term, which is likely categorized more completely than e.g. a plural or past tense verb.')
	parser.add_argument('-o', '--output-path', help='[required] The path of the file to write the IDs of selected terms to.')
	# g is the first untaken letter in 'starting terms'
	parser.add_argument('-g', '--initial-terms-path', help='The path of a text file containing an initial list of terms (or MediaWiki IDs of entries) to start with, one term per line. (If the first entry is numeric it will be assumed the terms are being given as entry IDs rather than the terms being given directly.) Required if --cats-path and --include-cats are not given.')
	parser.add_argument('-a', '--cats-path', help='The path of the CSV categories file (as produced by parse_cats.py) that should be used to find subcategories of explicitly mentioned categories. Required if --initial-terms-path is not given. Ignored if neither --include-cats nor --exclude-cats is given.')
	parser.add_argument('-i', '--include-cats', nargs='+', help='The titles of categories from which to collect selected terms. If you want to include all terms in a language, you can do this by including the categories "[Language name] lemmas" and "[Language name] non-lemma forms". Required if --initial-terms-path is not given. Requires --cats-path.')
	parser.add_argument('-e', '--exclude-cats', nargs='+', default=[], help='Terms in these categories (and their subcategories) will be excluded (overriding included categories). Requires --cats-path.')
	parser.add_argument('-d', '--depth', default=-1, type=int, help='The maximum depth to explore each category\'s descendants. By default there is no limit (indicated by a negative value). Zero means just immediate children, one means children and grandchildren, and so on. Ignored if neither --include-cats nor --exclude-cats is given.')
	# m for memory
	parser.add_argument('-m', '--small-ram', action='store_true', help='Indicates that not enough memory (RAM) is available to read all category associations into memory, so they should instead be repeatedly read from disk, even though this is slower. Otherwise this program may use several gigabytes of RAM. (In 2024-01 I ran this with all category associations for the English Wiktionary and it used about 8 GB of RAM.) Ignored if neither --include-cats nor --exclude-cats is given.')
	parser.add_argument('-x', '--regex', help='A regular expression that terms must fully match to be included. Matching is performed by Python\'s re.fullmatch(), so see that module\'s documentation for details. Note that the entire term must "fit within" the given regex, so if you want to find terms that merely *contain* a particular pattern, add .* at the beginning and end of your regex.')
	parser.add_argument('-l', '--lang-code', default='en', help='The ISO 639 code of the language for which to exclude labels and / or check a word\'s frequency. Defaults to "en" for English. Ignored if --exclude-labels is not also given.')
	# b is the second letter in the commonly used alias {{lb}}
	parser.add_argument('-b', '--exclude-labels', nargs='+', default=[], help='If a sense of a term has one of these labels, that sense will not support the inclusion of the term. (The term may still be included if it has other "valid" senses.) Labels are positional arguments of the {{label}} (AKA {{lb}}) template (excluding the language code). Requires --lang-code.')
	parser.add_argument('-t', '--exclude-temps', nargs='+', default=[], help='If a given template given here is used in a sense of a term, that sense will not support the inclusion of the term. (The term may still be included if it has other "valid" senses.)')
	# f for form-of
	parser.add_argument('-f', '--temps-cache-path', help='The path of a file in which to cache (and later retrieve) a list of templates required for form-of filtering.')
	# n for noun
	parser.add_argument('-n', '--parts-of-speech', nargs='+', default=[], help='If a sense is not one of these parts of speech (think noun, verb, etc) then it will not support the inclusion of a term. Case insensitive.')
	# j was the first untaken letter alphabetically
	parser.add_argument('-j', '--min-frequency', type=int, help='The minimum number of times a word must be used per 100 million words (according to wordfreq) to be included. This option only makes sense if you are excluding multiword terms. Requires --lang-code.')
	# u is the first untaken letter in 'output ids'
	parser.add_argument('-u', '--output-ids', action='store_true', help='Output the MediaWiki entry IDs of the selected entries rather than the titles of the entries.')
	# k was the first untaken letter alphabetically
	parser.add_argument('-k', '--sort', action='store_true', help='Sort the titles (case-insensitively) of the selected entries before writing them to the output file. Ignored if --output-ids is given.')
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

	required = ['stubs-path', 'redirects-path', 'pages-path', 'output-path']
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

	# Giving a key requires that its value also be given
	dependencies = {
		'include-cats': 'cats-path',
		'exclude-cats': 'cats-path',
		'exclude-labels': 'lang-code',
		'min-frequency': 'lang-code'
	}
	for used, req in dependencies.items():
		if getattr(config, used.replace('-', '_')) and not getattr(config, req.replace('-', '_')):
			raise ValueError(f'--{used} requires --{req}')

	if config.verbose:
		print(f'Reading stubs...')
	stub_master = parsing.parse_stubs.StubMaster(config.stubs_path)

	if config.cats_path and not config.small_ram:
		cat_master = parsing.parse_cats.CategoryMaster(config.cats_path, verbose=config.verbose)

	good_terms: list[int] = []
	if config.initial_terms_path:
		with open(config.initial_terms_path, encoding='utf-8') as initial_terms_file:
			first_line = next(initial_terms_file)[:-1]
			# Assume entry IDs are being given
			try:
				good_terms.append(int(first_line))
				for line in initial_terms_file:
					good_terms.append(int(line))
			# Terms are being given rather than entry IDs
			except ValueError:
				good_terms.append(stub_master.id(first_line))
				for line in initial_terms_file:
					good_terms.append(stub_master.id(line[:-1]))

	def deep_cat_proxy(cats: set[int], return_titles: bool, depth: int = config.depth):
		if config.small_ram:
			pages = deep_cat.deep_cat_filter_slow(config.cats_path, cats, return_titles=return_titles, max_depth=depth, verbose=config.verbose)
		else:
			pages = deep_cat.deep_cat_filter(cat_master, cats, return_titles=return_titles, max_depth=depth, verbose=config.verbose)
		return pages

	def cat_titles_to_ids(titles: collections.abc.Iterable[str]) -> set[int]:
		ids = set()
		for title in titles:
			ids.add(stub_master.id(title, parsing.parse_cats.CAT_NAMESPACE_ID))
		return ids

	if config.include_cats:
		include_cats = cat_titles_to_ids(config.include_cats)
		good_terms.extend(deep_cat_proxy(include_cats, return_titles=False))
	cat_bad_terms: set[int] = set()
	if config.exclude_cats:
		exclude_cats = cat_titles_to_ids(config.exclude_cats)
		cat_bad_terms = deep_cat_proxy(exclude_cats, return_titles=False)

	form_of_temps: set[str] = set()
	if config.temps_cache_path:
		# Attempt to read form-of templates
		try:
			with open(config.temps_cache_path, encoding='utf-8') as temps_cache_file:
				form_of_temps = set(temps_cache_file.read().splitlines())
		except FileNotFoundError:
			pass
	if not form_of_temps:
		if config.verbose:
			print('Finding all form-of templates and their aliases:')
		# Save form-of templates as titles rather than page IDs so that the cache file is human-readable
		form_of_temps_canonical_titles = deep_cat_proxy({FORM_OF_TEMP_CAT_ID}, return_titles=True)
		form_of_temps_canonical_titles_nses = {(parsing.parse_temps.TEMP_NAMESPACE_ID, temp_title) for temp_title in form_of_temps_canonical_titles}
		form_of_temps = {title for ns, title in parsing.parse_redirects.add_redirects(form_of_temps_canonical_titles_nses, config.redirects_path)}
	# Attempt to cache form-of templates
	try:
		with open(config.temps_cache_path, 'x', encoding='utf-8') as temps_cache_file:
			for temp in form_of_temps:
				print(temp, file=temps_cache_file)
	except FileExistsError:
		pass

	# Free up memory
	if config.cats_path and not config.small_ram:
		del cat_master

	term_filter = TermFilter(
		stub_master,
		config.pages_path,
		config.lang_code,
		config.redirects_path,
		form_of_temps=form_of_temps,
		bad_terms=cat_bad_terms,
		exclude_labels=set(config.exclude_labels),
		exclude_temps=config.exclude_temps,
		parts_of_speech=set(config.parts_of_speech),
		verbose=config.verbose
	)

	if config.verbose:
		print('Checking the senses of each term:')
	checked_terms: list[int] | list[str] = []
	for count, entry_id in enumerate(good_terms):
		if config.verbose and count % CHECK_VERBOSITY_FACTOR == 0:
			print(f'{count:,}')
		if not term_filter.check_entry(entry_id):
			continue
		# Regex and frequency filtering need to happen outside of TermFilter because a lemma failing one of these filters does not necessarily mean that its forms fail as well
		if config.regex and not re.fullmatch(config.regex, stub_master.title(entry_id)):
			continue
		if config.min_frequency and wordfreq.word_frequency(stub_master.title(entry_id), config.lang_code) * WORD_FREQ_FACTOR < config.min_frequency:
			continue
		checked_terms.append(entry_id)
	if not config.output_ids:
		checked_terms = [stub_master.title(entry_id) for entry_id in checked_terms]
		if config.sort:
			checked_terms.sort(key=str.casefold)

	if config.verbose:
		print('Writing selected terms...')
	with open(config.output_path, 'w', encoding='utf-8') as out_file:
		for entry in checked_terms:
			out_file.write(f'{entry}\n')

class Entry:
	def __init__(self, title: str):
		self.title = title
		self.senses: list[list[wikitextparser.Template]] = []

	def __iter__(self) -> collections.abc.Iterator[list[wikitextparser.Template]]:
		return iter(self.senses)

	def add_senses(self, more_senses: list[list[wikitextparser.Template]]) -> None:
		self.senses.extend(more_senses)

class TermFilter:
	def __init__(self,
			stub_master: parsing.parse_stubs.StubMaster,
			pages_path: str,
			lang_code: str,
			redirects_path: str,
			form_of_temps: set[str] | None = None,
			bad_terms: collections.abc.Collection[int] | None = None,
			exclude_labels: collections.abc.Container[str] | None = None,
			exclude_temps: collections.abc.Iterable[str] | None = None,
			parts_of_speech: collections.abc.Container[str] | None = None,
			verbose: bool = False):

		self.stub_master = stub_master
		self.pages_path = pages_path
		self.lang_code = lang_code
		self.redirects_path = redirects_path
		self.form_of_temps = form_of_temps or set()
		self.cache: dict[int, bool] = {id_: False for id_ in bad_terms} if bad_terms else {}
		self.exclude_labels = exclude_labels or set()
		self.exclude_temps: set[str] = set()
		if exclude_temps:
			temps_with_nses = {(parsing.parse_temps.TEMP_NAMESPACE_ID, temp) for temp in exclude_temps}
			for temp_with_ns in parsing.parse_redirects.add_redirects(temps_with_nses, self.redirects_path):
				self.exclude_temps.add(temp_with_ns[1])
		self.parts_of_speech = parts_of_speech or set()
		self.verbose = verbose
		self.read_entries()

	def check_entry(self, term: int | str, time_to_live: int = 4) -> bool:
		if isinstance(term, str):
			try:
				term_id = self.stub_master.id(term)
			except KeyError:
				return False
		else:
			term_id = term

		if term_id not in self.cache:
			self.cache[term_id] = self.check_uncached_term(term_id, time_to_live)
		return self.cache[term_id]

	def check_uncached_term(self, term_id: int, time_to_live: int = 4) -> bool:
		# If after following a few links we still haven't found a lemma, assume we are in a cycle and accept the term
		if time_to_live <= 0:
			return True
		if term_id not in self.entries:
			return False

		for sense in self.entries[term_id]:
			if any(temp.normal_name() in self.exclude_temps for temp in sense):
				continue
			try:
				label_temp = next(temp for temp in sense if temp.normal_name() in LABEL_TEMPS and temp.get_arg('1').positional and temp.get_arg('1').value == self.lang_code)
				if any((arg.value in self.exclude_labels) for arg in label_temp.arguments[1:] if arg.positional):
					continue
			except StopIteration:
				pass
			try:
				form_of_temp = next(temp for temp in sense if temp.normal_name() in self.form_of_temps)
				main_form = (form_of_temp.get_arg('2') or form_of_temp.get_arg('1')).value
				if not self.check_entry(main_form, time_to_live - 1):
					continue
			except StopIteration:
				pass
			return True
		return False

	@staticmethod
	def temps_in_section(section: str) -> list[list[wikitextparser.Template]]:
		# Empty sublists are intentionally preserved
		return [wikitextparser.parse(line).templates for line in section.splitlines() if line.startswith('# ')]

	def read_entries(self) -> None:
		if self.verbose:
			print('\nLoading pages data:')

		self.entries: dict[int, Entry] = {}
		for count, page in enumerate(parsing.etree_helpers.pages_gen(self.pages_path)):
			if self.verbose and count % PAGES_VERBOSITY_FACTOR == 0:
				print(f'{count:,}')

			page_id = int(page.findtext('./id'))
			page_title = page.findtext('./title')
			page_text = page.findtext('./revision/text')
			if self.cache.get(page_id, True) and page_text:
				entry = Entry(page_title)
				if self.parts_of_speech:
					# Assume parsing.lang been used to remove all L2 sections except for the relevant one
					wikitext: wikitextparser.Section = wikitextparser.parse(page_text).get_sections(level=2)[0]
					for section in wikitext.get_sections(level=3):
						# Multiple etymologies
						if re.fullmatch(r'Etymology \d+', section.title):
							for subsection in section.get_sections(level=4):
								if subsection.title.casefold() in self.parts_of_speech:
									entry.add_senses(self.temps_in_section(subsection.contents))
						# Single etymology
						else:
							if section.title.casefold() in self.parts_of_speech:
								entry.add_senses(self.temps_in_section(section.contents))
				# No parts of speech specified
				else:
					entry.add_senses(self.temps_in_section(page_text))

				if entry.senses:
					self.entries[page_id] = entry

			page.clear()

# End of TermFilter

if __name__ == '__main__':
	main()
