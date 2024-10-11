import argparse
import collections
import functools
import json
import re

import wikitextparser

import etree_helpers

VERBOSITY_FACTOR = 10 ** 5
GOOD_PARTS_OF_SPEECH = ['adjective', 'adverb', 'interjection', 'noun', 'verb']
PARTS_OF_SPEECH = {
	'adjective',
	'adverb',
	'ambiposition',
	'article',
	'circumposition',
	'classifier',
	'conjunction',
	'contraction',
	'counter',
	'determiner',
	'ideophone',
	'interjection',
	'noun',
	'numeral',
	'participle',
	'particle',
	'postposition',
	'preposition',
	'pronoun',
	'proper noun',
	'verb'
}
RHYME_TEMP_NAMES = ['rhymes', 'rhyme']
RHYME_CAT_PREFIX = 'Rhymes:English/'

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('rhyme_ids_path', help='Path of the file containing entry IDs (one per line) of terms which have rhymes, as produced by using deep_cat to find all entries in Category:Rhymes:English.')
	parser.add_argument('pages_path', help='Path of the XML file containing the text of each entry, in order to determine predominant parts of speech.')
	parser.add_argument('good_ids_path', help='Path of the file containing entry IDs (one per line) of terms considered acceptable replacements, as produced by find_terms.')
	parser.add_argument('frequencies_path', help='Path of the JSON file containing word frequencies, as pdocued by find_frequencies.')
	parser.add_argument('-l', '--language', default='English', help='The name of the language as it appears in the heading of each entry.')
	parser.add_argument('output_path', help='Path of the file to write the rhyme category data to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Reading IDs of terms with rhymes...')
	with open(args.rhyme_ids_path, encoding='utf-8') as rhyme_ids_file:
		rhyme_ids = {int(id_) for id_ in rhyme_ids_file.read().splitlines()}

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
	word_rhymes = collections.defaultdict(dict)
	for page_count, page in enumerate(etree_helpers.pages_gen(args.pages_path)):
		try:
			page_id = int(etree_helpers.find_child(page, 'id').text)
			page_title = etree_helpers.find_child(page, 'title').text
			# [!-~] matches all printable, non-whitespace ASCII characters
			if not re.fullmatch(r'[!-~]+', page_title):
				continue
			text = etree_helpers.find_child(etree_helpers.find_child(page, 'revision'), 'text').text
			wikitext = wikitextparser.parse(text)
			lang_sec = next(sec for sec in wikitext.get_sections(level=2) if sec.title == args.language)

			# Find predominant part of speech
			# If part of speech is not recognized this field is set to None, indicating the word is a function word
			part_of_speech = next((sec.title.lower() for sec in lang_sec.sections if (sec.level == 3 or sec.level == 4) and sec.title.lower() in PARTS_OF_SPEECH), None)
			word_rhymes[page_title]['part of speech'] = part_of_speech if part_of_speech in GOOD_PARTS_OF_SPEECH else None

			# Find rhymes
			if page_id in rhyme_ids:
				word_rhymes[page_title]['rhymes'] = collections.defaultdict(list)
				for temp in lang_sec.templates:
					if temp.normal_name() in RHYME_TEMP_NAMES:
						# Skip over the first argument since it is the language code
						temp_rhymes = [arg.value for arg in temp.arguments if arg.positional][1:]
						for i, rhyme in enumerate(temp_rhymes, start=1):
							syllable_count_arg = temp.get_arg(f's{i}') or temp.get_arg('s')
							if syllable_count_arg:
								for syllable_count in syllable_count_arg.value.split(','):
									# We could convert syllable_count to an int here, but there's no point since it will get converted back to a string in JSON
									word_rhymes[page_title]['rhymes'][syllable_count].append(rhyme)
				if page_id in good_ids and part_of_speech:
					word_rhymes[page_title]['frequency'] = frequencies.get(page_title, 0)

		finally:
			if args.verbose and page_count % VERBOSITY_FACTOR == 0:
				print(f'{page_count:,}')
			page.clear()

	with open(args.output_path, 'w', encoding='utf-8') as word_rhymes_file:
		json.dump(word_rhymes, word_rhymes_file, indent='\t')

if __name__ == '__main__':
	main()
