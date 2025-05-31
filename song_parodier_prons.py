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
	# Short vowel marker listed at [[wikipedia:International Phonetic Alphabet]]
	'\u0306',
	# Short vowel marker used in practice on Wiktionary
	'\u032F',
	# Tie
	'\u0361',
	# Indicates a consonant is syllabic
	'\u0329',
	# Keep optional phonemes
	'(', ')'
]
PRON_TRANS = str.maketrans('', '', ''.join(PRON_CHARS_TO_REMOVE))

# This is a few of the most common accents from [[Module:labels/data/lang/en]]
DEALIAS_ACCENT = {
	**dict.fromkeys(['GenAm', 'GA'], 'General American'),
	**dict.fromkeys(['RP'], 'Received Pronunciation'),
	**dict.fromkeys(['CA', 'Canadian', 'CanE', 'Canadian English'], 'Canada'),
	**dict.fromkeys(['U.S.', 'United States', 'United States of America', 'USA', 'US English', 'U.S. English', 'America', 'American', 'American English'], 'US'),
	**dict.fromkeys(['Australian', 'AU', 'AuE', 'Aus', 'AusE', 'General Australian'], 'Australia'),
	**dict.fromkeys(['NZ', 'NZE'], 'New Zealand'),
	**dict.fromkeys(['United Kingdom'], 'UK')
}

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path', help='Path of the XML file containing the text of each entry, in order to find pronunciations.')
	parser.add_argument('good_ids_path', help='Path of the file containing entry IDs (one per line) of terms considered acceptable replacements, as produced by find_terms.')
	parser.add_argument('frequencies_path', help='Path of the JSON file containing word frequencies, as produced by find_frequencies.')
	parser.add_argument('-a', '--accents', nargs='+', default=[], help='The accents of English (as they appear next to IPA pronunciations on Wiktionary) to look for pronunciations in. Pronunciations in other accents will be excluded, but pronunciations with no accent specified will be included.')
	parser.add_argument('-l', '--language', default='English', help='The name of the language as it appears in the heading of each entry. Defaults to "English".')
	parser.add_argument('output_path', help='Path of the file to write the pronunciation data to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	args.accents = [DEALIAS_ACCENT.get(acc, acc) for acc in args.accents]

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
			prons = []
			for temp in pron_sec.templates:
				if temp.normal_name() != 'IPA':
					continue
				# Skip over the first argument since it is the language code
				temp_prons = [arg.value for arg in temp.arguments if arg.positional][1:]

				general_accent = temp.get_arg('a')
				for i, pron in enumerate(temp_prons, start=1):
					if args.accents:
						accent_arg = temp.get_arg(f'a{i}') or general_accent
						if accent_arg and not any(DEALIAS_ACCENT.get(accent, accent) in args.accents for accent in accent_arg.value.split(',')):
								continue
					if not (pron.startswith('/') and pron.endswith('/')):
						continue
					pron = pron[1:-1]
					if pron.startswith('-') or pron.endswith('-'):
						continue
					pron = pron.translate(PRON_TRANS)
					if pron not in prons:
						prons.append(pron)

			pron_data[page_title]['pronunciations'] = prons
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
