'''
Filter terms in a specific language out of an XML file.
'''

import argparse
import typing
import xml.etree.ElementTree as xet

import wikitextparser

import parsing.etree_helpers
import parsing.parse_cats

CAT_VERBOSE_FACTOR = 10 ** 6
PAGE_VERBOSE_FACTOR = 10 ** 5

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path', help='The XML pages file to parse.')
	parser.add_argument('output_path', help='The XML pages file to write to.')
	parser.add_argument('-l', '--language', default='English', help='The full name (*not* ISO code) of the language to select. Defaults to English.')
	parser.add_argument('-c', '--cats-path', help='The CSV file containing category membership data, as produced by parse_cats. Providing this will cause pages to be selected based on whether they are in the categories of the selected language. Otherwise all pages are parsed to see if they have headings for the selected languages.')
	parser.add_argument('-v', '--verbose', action='store_true', help='Prints occasional progress updates.')
	args = parser.parse_args()

	language_filter(args.input_path, args.output_path, args.language, args.cats_path, args.verbose)

def language_filter(input_path: str, output_path: str, language: str = 'English', cats_path: str | None = None, verbose: bool = False) -> None:
	target_cats = [f'{language} lemmas', f'{language} non-lemma forms']
	target_pages: set[int] = set()
	if verbose:
		print('Reading in category data:')
	if cats_path:
		for cat_count, cat_link in enumerate(parsing.parse_cats.cats_gen(cats_path)):
			if verbose and cat_count % CAT_VERBOSE_FACTOR == 0:
				print(f'{cat_count:,}')
			if cat_link.cat_title in target_cats:
				target_pages.add(cat_link.page_id)
		if verbose:
			print(f'Found {len(target_pages):,} {language} terms.')

	if verbose:
		print('Filtering pages:')
	with open(output_path, 'w', encoding='utf-8') as out_file:
		out_file.write('<mediawiki>\n  ')
		for page_count, page in enumerate(parsing.etree_helpers.pages_gen(input_path)):
			if verbose and page_count % PAGE_VERBOSE_FACTOR == 0:
				print(f'{page_count:,}')

			page_id = int(page.findtext('./id'))
			if cats_path and page_id not in target_pages:
				continue
			text_elem = page.find('./revision/text')
			# As of Python 3.13 elements with no children are falsey, so direct comparison with None is necessary here
			# Perform a fast substring search first to avoid parsing most irrelevant pages
			if text_elem != None and text_elem.text and language in text_elem.text:
				wikitext = wikitextparser.parse(text_elem.text)
				for section in wikitext.get_sections(level=2):
					section_title = section.title.strip()
					# Any text before the first heading will be considered its own section with an empty title
					if section_title and section_title == language:
						text_elem.text = str(section)
						page_xml = xet.tostring(page, encoding='unicode')
						out_file.write(f'{page_xml}')
						break

		out_file.write('</mediawiki>\n')

if __name__ == '__main__':
	main()
