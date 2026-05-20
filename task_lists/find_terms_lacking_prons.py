'''
Find common words that lack pronunciations in the English Wiktionary, so that I can add pronunciations to them. Commonality is determined by word frequencies created by find_frequencies using data from Wikisource.
'''

import argparse
import json

import wikitextparser

import parsing.etree_helpers
import parsing.parse_redirects

FREQUENCY_THRESHOLD = 100
VERBOSE_FACTOR = 10 ** 5

SPELLING_FORM_OF_TEMPS = [
	'alternative case form of',
	'alternative spelling of',
	'archaic spelling of',
	'dated spelling of',
	'deliberate misspelling of',
	'honorific alternative case form of',
	'informal spelling of',
	'medieval spelling of',
	'misspelling of',
	'nonstandard spelling of',
	'obsolete spelling of',
	'rare spelling of',
	'spelling of',
	'standard spelling of',
	'superseded spelling of',
	'uncommon spelling of'
]

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path', help='Path of the XML file containing the wikitext of entries to check for existing pronunciations.')
	parser.add_argument('freqs_path', help='Path of a JSON file mapping words to their frequencies.')
	parser.add_argument('redirects_path', help='Path of a CSV file containing redirects, as produced by parse_redirects.')
	parser.add_argument('output_path', help='Path to write the wikitext list of results to.')
	parser.add_argument('-l', '--lowercase', action='store_true', help='Lowercase terms when looking up their frequencies. Intended to be used in conjunction with the same option of find_frequencies.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	with open(args.freqs_path, encoding='utf-8') as freq_file:
		frequencies: dict[str, int] = json.load(freq_file)

	form_of_temps_with_ns = {(10, temp) for temp in SPELLING_FORM_OF_TEMPS}
	form_of_temps_with_redirects: set[(int, str)] = parsing.parse_redirects.add_redirects(form_of_temps_with_ns, args.redirects_path)
	form_of_temps: set[str] = {pair[1] for pair in form_of_temps_with_redirects}

	def freq(term: str) -> int:
		return frequencies.get(page_title.casefold() if args.lowercase else page_title, 0)

	terms_lacking_prons = []
	for count, page in enumerate(parsing.etree_helpers.pages_gen(args.pages_path)):
		if args.verbose and count % VERBOSE_FACTOR == 0:
			print(f'{count:,}')

		page_title = page.findtext('./title')
		# All-caps terms tend to be acronyms, pronounced as their individual letters
		# Numeric terms tend to be pronounced as numbers or digits
		if ' ' not in page_title and '-' not in page_title and not page_title.isupper() and not page_title.isnumeric() and freq(page_title) >= FREQUENCY_THRESHOLD:
			text = page.findtext('./revision/text')
			if not text:
				continue
			wikitext = wikitextparser.parse(text)
			lang_section = next(sec for sec in wikitext.get_sections(level=2) if sec.title == 'English')
			if any(section.title == 'Pronunciation' and 3 <= section.level <= 5 for section in lang_section.sections):
				continue

			# Look for a sense that is not a spelling-form-of template
			has_valid_sense = False
			for sense_list in lang_section.get_lists('\#'):
				for sense in sense_list.items:
					sense_temps = wikitextparser.parse(sense).templates
					if {temp.normal_name() for temp in sense_temps}.isdisjoint(form_of_temps):
						has_valid_sense = True
			if not has_valid_sense:
				continue
			terms_lacking_prons.append(page_title.casefold() if args.lowercase else page_title)

	terms_lacking_prons.sort(key=freq, reverse=True)

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for term in terms_lacking_prons:
			print(term, file=out_file)

if __name__ == '__main__':
	main()
