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

	target_cats = [f'{args.language} lemmas', f'{args.language} non-lemma forms']
	target_pages = set()
	if args.verbose:
		print('Reading in category data:')
	if args.cats_path:
		for cat_count, cat_link in enumerate(parsing.parse_cats.cats_gen(args.cats_path)):
			if cat_link.cat_title in target_cats:
				target_pages.add(cat_link.page_id)
			if args.verbose and cat_count % CAT_VERBOSE_FACTOR == 0:
				print(f'{cat_count:,}')
	if args.verbose:
		print(f'Found {len(target_pages):,} {args.language} terms.')

	if args.verbose:
		print('Filtering pages:')
	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		out_file.write('<mediawiki>\n  ')
		for page_count, page in enumerate(parsing.etree_helpers.pages_gen(args.input_path)):
			is_target = False
			if args.cats_path:
				page_id = int(parsing.etree_helpers.find_child(page, 'id').text)
				if page_id in target_pages:
					is_target = True
			else:
				text_elem = parsing.etree_helpers.find_child(parsing.etree_helpers.find_child(page, 'revision'), 'text')
				# Perform a fast substring search first to avoid parsing most irrelevant pages
				if args.language in text_elem.text:
					parsed = wikitextparser.parse(text_elem.text)
					if any(True for section in parsed.get_sections(level=2) if section.title == args.language):
						is_target = True

			if is_target:
				page_xml = xet.tostring(page, encoding='unicode')
				out_file.write(page_xml)
				out_file.write('\n  ')

			page.clear()
			if args.verbose and page_count % PAGE_VERBOSE_FACTOR == 0:
				print(f'{page_count:,}')

		out_file.write('\n</mediawiki>\n')

if __name__ == '__main__':
	main()
