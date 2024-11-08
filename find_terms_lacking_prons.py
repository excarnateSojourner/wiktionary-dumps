import argparse
import json

import wikitextparser

import etree_helpers

FREQUENCY_THRESHOLD = 256
VERBOSE_FACTOR = 10 ** 5

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path')
	parser.add_argument('freqs_path')
	parser.add_argument('output_path')
	parser.add_argument('-l', '--lowercase', action='store_true', help='Lowercase terms when looking up their frequencies. Intended to be used in conjunction with the same option of find_frequencies.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	with open(args.freqs_path, encoding='utf-8') as freq_file:
		frequencies: dict[str, int] = json.load(freq_file)

	def freq(term: str) -> int:
		return freqs.get(page_title.casefold() if args.lowercase else page_title, 0)

	terms_lacking_prons = []
	for count, page in enumerate(etree_helpers.pages_gen(args.pages_path)):
		page_title = etree_helpers.find_child(page, 'title').text
		if page_title.isalnum() and freq(page_title) >= FREQUENCY_THRESHOLD:
			text = etree_helpers.find_child(etree_helpers.find_child(page, 'revision'), 'text').text
			wikitext = wikitextparser.parse(text)
			lang_section = next(sec for sec in wikitext.get_sections(level=2) if sec.title == 'English')
			if not any(section.title == 'Pronunciation' and 3 <= section.level <= 5 for section in lang_section.sections):
				terms_lacking_prons.append(page_title.casefold() if args.lowercase else page_title)
		page.clear()

		if args.verbose and count % VERBOSE_FACTOR == 0:
			print(f'{count:,}')

	terms_lacking_prons.sort(key=freq, reverse=True)
	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for term in terms_lacking_prons:
			print(term, file=out_file)

if __name__ == '__main__':
	main()
