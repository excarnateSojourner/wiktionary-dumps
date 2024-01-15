import argparse
import collections
import importlib
import itertools
import re
import subprocess
import xml.dom
import xml.dom.pulldom

import parse_cats
import pulldom_helpers

# English 2-syllable words
INCLUDE_CATS = {5834597}
# English prefix forms, English suffix forms, English affixes, English circumfixes, English clitics, English infixes, English interfixes, English prefixes, English suffixes
EXCLUDE_CATS = {52195, 78364, 93234, 261835, 600201, 1600728, 4553094, 6334781, 8734636}
MAIN_VERBOSE_FACTOR = 10 ** 3
SKIPPING_VERBOSE_FACTOR = 10 ** 4

VOWELS = 'aeiouæɑɒɔəɚɛɜɝɪʊʌ'
# the only ASCII char in NON_RHYME_CHARS is a space, even though others may appear to be ASCII
NON_RHYME_CHARS = '.ˈˌ ͡'
CONSONANTS = 'bdfhkjlmnpstvwzðŋɡɹʃʒʔθ'
STANDARD_CHARS = '()ː' + CONSONANTS + VOWELS + NON_RHYME_CHARS
STANDARD_PRON = r'/[' + STANDARD_CHARS + r']+/'
PRON_TO_RHYME = r'[' + STANDARD_CHARS + ']*?(\(?[' + VOWELS + r'][' + STANDARD_CHARS + ']*)/$'

def main():

	parser = argparse.ArgumentParser()
	parser.add_argument('-p', '--pages-path', required=True, help='The path of an XML file containing MediaWiki page text to search through.')
	parser.add_argument('-c', '--categories-path', help='The path of a CSV file containing category associations, as produced by parse_cats.py.')
	parser.add_argument('-r', '--prons-path', required=True, help='The path of a text file containing all English pronunciations.')
	parser.add_argument('-o', '--output-path', required=True, help='The path of a MediaWiki file to write the words lacking rhymes to. They will be automatically formatted as links listed in five columns. This file will be created if it does not exist, and *overwritten without warning* if it does.')
	parser.add_argument('-w', '--word-cache-path', help='The path of a text file in which to cache the contents of categories relevant to finding words without rhymes. (It will be created if it does not exist.)')
	parser.add_argument('-f', '--refresh-cache', action='store_true', help='Force a refresh of the cache, even if it appears to be up to date.')
	parser.add_argument('-i', '--start-id', type=int, help='Skip over all pages with ID less than this.')
	parser.add_argument('-v', '--verbose', action='store_true', help='Print the words lacking rhymes to stdout as they are found.')
	parser.add_argument('-e', '--example-count', default=4, type=int, help='Specify the number of example words to give that probably rhyme with the target word. Defaults to 4.')
	args = parser.parse_args()
	if not args.categories_path and not args.word_cache_path:
		raise ValueError('At least one of --category-path (-c) and --word-cache-path (-w) must be provided.')

	words = find_rhymeless_words(args)

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		print('{|class="wikitable"', '!Word', '!Suggested template', '!Rhymes', '!Rhyming pronunciation count', '!Rhyming pronunciation examples', '|-', sep='\n', file=out_file)
		for word, prons in words:
			rhyme_siblings = {}
			try:
				rhymes = prons_to_rhymes(prons)
			except ValueError:
				write_table_row(word, {}, out_file)
				continue
			for rhyme in rhymes:
				siblings = find_siblings(rhyme, args)
				if len(siblings) > 1:
					rhyme_siblings[rhyme] = (len(siblings), siblings[:args.example_count])
			if rhyme_siblings:
				write_table_row(word, rhyme_siblings, out_file)
		print('|}', file=out_file)

def find_rhymeless_words(args):
	catted_words = find_categorized_words(args)
	doc = xml.dom.pulldom.parse(args.pages_path)
	for event, node in doc:
		if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'page':
			doc.expandNode(node)
			page_id = int(pulldom_helpers.get_descendant_text(node, 'id'))
			if args.start_id and page_id < args.start_id:
				if args.verbose and page_id % SKIPPING_VERBOSE_FACTOR == 0:
					print(f'Skipping ID {page_id}...')
				continue
			elif args.verbose and page_id % MAIN_VERBOSE_FACTOR == 0:
				print(f'Processing ID {page_id}...')
			title = pulldom_helpers.get_descendant_text(node, 'title')
			text = pulldom_helpers.get_descendant_text(node, 'text')
			if page_id in catted_words and ('{{IPA|en|' in text or '{{ipa|en|' in text) and not ('{{rhymes|en|' in text or '{{rhyme|en|' in text):
				prons = []
				for pron_set in re.findall('{{IPA\|en\|(.*?)}}', text, flags=re.IGNORECASE):
					prons.extend(pron_set.split('|'))
				yield (title, prons)

def find_siblings(rhyme, args):
	process = subprocess.run(['grep', '-P', f'(ˈ|/[ˈ{CONSONANTS}]*){rhyme}/', args.prons_path], capture_output=True)
	return process.stdout.decode().splitlines()

def write_table_row(word, rhyme_siblings, out_file):
	def print_row(*strs, **kwargs):
		print(*(f'|{s}' for s in strs), sep='\n', file=out_file, **kwargs)

	if rhyme_siblings:
		if len(rhyme_siblings) == 1:
			print_row(f'{{{{l|en|{word}}}}}')
			print_row('<code><nowiki>* {{rhymes|en|' + '|'.join(rhyme_siblings) + '|s=2}}</nowiki></code>')
		else:
			rowspan = f'rowspan="{len(rhyme_siblings)}"|'
			print_row(f'{rowspan}{{{{l|en|{word}}}}}')
			print_row(rowspan + '<code><nowiki>* {{rhymes|en|' + '|'.join(rhyme_siblings) + '|s=2}}</nowiki></code>')
		for rhyme, siblings in rhyme_siblings.items():
			print_row('{{IPAchar|/-' + rhyme + '/}}')
			print_row(siblings[0])
			print_row('; '.join('{{IPAchar|' + example + '}}' for example in siblings[1]))
			print_row('-')
	else:
		print_row(f'{{{{l|en|{word}}}}}')
		print_row('\n|\n|\n|\n|-')

def prons_to_rhymes (prons):
	'''Extracts the corresponding rhyme for each of the IPA pronunciations in prons, and:
	* combines rhymes that differ only in their inclusion of an 'ɹ';
	* expands rhymes containing non-(ɹ) parentheticals into multiple rhymes;
	* deduplicates the rhymes.'''
	phonemic_prons = []
	for i, pron in enumerate(prons):
		if not (pron.startswith('[') or pron.endswith(']')):
			if re.fullmatch(STANDARD_PRON, pron):
				pron = pron.replace('ɚ', 'ə(ɹ)')
				pron = pron.replace('ɝ', 'ɜ(ɹ)')
				phonemic_prons.append(pron)

	rhymes = []
	for pron in phonemic_prons:
		# find primary stress indicated
		try:
			rhymes.append(re.search('ˈ' + PRON_TO_RHYME, pron)[1])
		# primary stress not indicated
		except TypeError:
			pass

	rm_nonrhyme_chars = str.maketrans('', '', NON_RHYME_CHARS)
	rhymes = [rhyme.translate(rm_nonrhyme_chars) for rhyme in rhymes]

	# deduplicate
	rhymes = list(dict.fromkeys(rhymes))

	rhymes = combine_on_r(rhymes)
	rhymes = itertools.chain.from_iterable(expand_parens(rhyme) for rhyme in rhymes)

	# deduplicate
	return list(dict.fromkeys(rhymes))

def combine_on_r (rhymes):
	'''Takes a list of rhymes and properly combines rhymes that differ only in their inclusion of 'ɹ' (and possibly a long vowel symbol). If any rhyme has more than one instance of 'ɹ', it is a ValueError.'''
	combined = []

	def add_with_and_without_long_vowel(before, after):
		combs.append(before + after)
		if before.endswith('ː'):
			combs.append(before.rstrip('ː') + after)
		else:
			combs.append(before + 'ː' + after)

	def find_comb_match(rhyme0, combs):
		for i, rhyme1 in enumerate(rhymes):
			if rhyme1:
				for comb in combs:
					if rhyme1 == comb:
						rhymes[i] = None
						before, after = re.split('\(?ɹ\)?', rhyme0)
						# if rhyme0 or comb has a long vowel symbol before the 'ɹ'
						if before.endswith('ː') or re.search('ː\(?ɹ', comb):
							return before + 'ː(ɹ)' + after
						else:
							return before + '(ɹ)' + after

	remaining = rhymes.copy()
	for rhyme0 in rhymes:
		if rhyme0:
			# if rhyme0 contains one 'ɹ'
			if (r_count := rhyme0.count('ɹ')) == 1:
				before, after = rhyme0.split('ɹ', maxsplit=1)
				combs = []
				if before.endswith('(') and after.startswith(')'):
					before = before[:-1]
					after = after[1:]
					add_with_and_without_long_vowel(before, 'ɹ' + after)
				else:
					add_with_and_without_long_vowel(before, '(ɹ)' + after)
				add_with_and_without_long_vowel(before, after)
				melded = find_comb_match(rhyme0, combs)
				combined.append(melded if melded else rhyme0)
			# rhyme0 contains more than one 'ɹ'
			elif r_count > 1:
				raise ValueError('One of the rhymes includes more than one instance of /ɹ/.')

	return combined + [rhyme for rhyme in rhymes if rhyme and 'ɹ' not in rhyme]

def expand_parens (s):
	'''Return a list of strings containing all combinations of including and excluding each of the parentheticals in s.'''
	parts = re.split(r'\(([^ɹ])\)', s, maxsplit=1)
	# if no parentheticals
	if len(parts) < 3:
		return [s]
	# if parenthetical found
	else:
		combs = []
		for comb in expand_parens(parts[2]):
			combs.append(parts[0] + comb)
			combs.append(parts[0] + parts[1] + comb)
		return combs

def find_categorized_words(args):
	if args.word_cache_path and not args.refresh_cache:
		try:
			with open(args.word_cache_path, encoding='utf-8') as cache_file:
				return set(int(line[:-1]) for line in cache_file)
		except FileNotFoundError:
			pass

	# cache is missing or outdated, so we need to refresh it
	include_words = set()
	exclude_words = set()
	for data in parse_cats.cats_gen(args.categories_path):
		if data.cat_id in INCLUDE_CATS:
			include_words.add(data.page_id)
		elif data.cat_id in EXCLUDE_CATS:
			exclude_words.add(data.page_id)
	words = include_words - exclude_words

	if args.word_cache_path:
		with open(args.word_cache_path, 'w', encoding='utf-8') as cache_file:
			for word in words:
				print(word, file=cache_file)

	return words

if __name__ == '__main__':
	main()
