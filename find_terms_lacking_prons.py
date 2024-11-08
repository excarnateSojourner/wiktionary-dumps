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
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	with open(args.freqs_path, encoding='utf-8') as freq_file:
		freqs = json.load(freq_file)

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for count, page in enumerate(etree_helpers.pages_gen(args.pages_path)):
			page_title = etree_helpers.find_child(page, 'title').text
			if page_title.isalnum() and not page_title.isupper() and not page_title.isnumeric() and freq(page_title) >= FREQUENCY_THRESHOLD:
				text = etree_helpers.find_child(etree_helpers.find_child(page, 'revision'), 'text').text
				wikitext = wikitextparser.parse(text)
				lang_section = next(sec for sec in wikitext.get_sections(level=2) if sec.title == 'English')
				if not any(section.title == 'Pronunciation' and 3 <= section.level <= 5 for section in lang_section.sections):
					print(page_title, file=out_file)
			page.clear()

			if args.verbose and count % VERBOSE_FACTOR == 0:
				print(f'{count:,}')

if __name__ == '__main__':
	main()
