import argparse
import collections
import json
import re

import wikitextparser

import deep_cat
import parsing.etree_helpers

VERBOSITY_FACTOR = 10 ** 5
PRON_CHARS_TO_REMOVE = [
	# Primary stress marker
	'\u02C8',
	# Secondary stress marker
	'\u02CC',
	# Syllable separator (normal ASCII period)
	'.',
	# Space
	' ',
	# Long vowel marker
	'\u02D0',
	# Half-long vowel marker
	'\u02D1',
	# Short vowel marker
	'\u0306',
	# Tie
	'\u0361',
	# Indicates a consonant is syllabic
	'\u0329',
	# Keep optional phonemes
	'(', ')'
]
PRON_TRANS = str.maketrans('', '', ''.join(PRON_CHARS_TO_REMOVE))

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path', help='Path of the XML file containing the text of each entry, in order to find pronunciations.')
	parser.add_argument('good_ids_path', help='Path of the file containing entry IDs (one per line) of terms considered acceptable replacements, as produced by find_terms.')
	parser.add_argument('frequencies_path', help='Path of the JSON file containing word frequencies, as produced by find_frequencies.')
	parser.add_argument('-l', '--language', default='English', help='The name of the language as it appears in the heading of each entry. Defaults to "English".')
	parser.add_argument('output_path', help='Path of the file to write the pronunciation data to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Reading IDs of good words...')
	with open(args.good_ids_path, encoding='utf-8') as good_ids_file:
		good_ids = {int(id_) for id_ in good_ids_file.read().splitlines()}

	if args.verbose:
		print('Reading word frequencies...')
	with open(args.frequencies_path, encoding='utf-8') as frequencies_file:
		frequencies: dict[str, int] = json.load(frequencies_file)

	if args.verbose:
		print('Reading entries:')
	pron_data: dict[str, dict] = collections.defaultdict(dict)
	for page_count, page in enumerate(parsing.etree_helpers.pages_gen(args.pages_path)):
		try:
			page_id = int(parsing.etree_helpers.find_child(page, 'id').text)
			page_title = parsing.etree_helpers.find_child(page, 'title').text
			# [!-~] matches all printable, non-whitespace ASCII characters
			if not re.fullmatch(r'[!-~]+', page_title):
				continue
			text = parsing.etree_helpers.find_child(parsing.etree_helpers.find_child(page, 'revision'), 'text').text
			wikitext = wikitextparser.parse(text)
			try:
				lang_sec = next(sec for sec in wikitext.get_sections(level=2) if sec.title == args.language)
				pron_sec = next(sec for sec in lang_sec.sections if 3 <= sec.level <= 4 and sec.title == 'Pronunciation')
			except StopIteration:
				continue

			# Find pronunciations
			prons = set()
			for temp in pron_sec.templates:
				if temp.normal_name() != 'IPA':
					continue
				# Skip over the first argument since it is the language code
				temp_prons = [arg.value for arg in temp.arguments if arg.positional][1:]
				for pron in temp_prons:
					if pron.startswith('/') and pron.endswith('/'):
						pron = pron[1:-1].translate(PRON_TRANS)
						prons.add(pron)
			pron_data[page_title]['pronunciations'] = list(prons)
			if page_id in good_ids:
				pron_data[page_title]['frequency'] = frequencies.get(page_title.casefold(), 0)

		finally:
			if args.verbose and page_count % VERBOSITY_FACTOR == 0:
				print(f'{page_count:,}')
			page.clear()

	with open(args.output_path, 'w', encoding='utf-8') as pron_data_file:
		json.dump(pron_data, pron_data_file, indent='\t')

if __name__ == '__main__':
	main()
