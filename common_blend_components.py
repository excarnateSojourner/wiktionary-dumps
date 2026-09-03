'''
Find words that commonly form blends using the {{blend}} template.
This was motivated by: https://en.wiktionary.org/wiki/Talk:-cest#RFD_discussion:_May%E2%80%93August_2026
Results from this script have been posted at: https://en.wiktionary.org/wiki/User:ExcarnateSojourner/Common_blend_components
'''

import argparse
import collections
import heapq
import xml.etree.ElementTree as xet

import wikitextparser

import deep_cat
import parsing.etree_helpers

ENGLISH_BLENDS_ID = 1613234

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('cats_path', help='Path of the CSV categories file as produced by parse_cats.')
	parser.add_argument('pages_path', help='Path of the XML pages file.')
	parser.add_argument('output_path', help='Path of the MediaWiki markup output file.')
	parser.add_argument('-n', '--output-count', default=100, type=int, help='The maximum number of blend components to give.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	blends = deep_cat.deep_cat_filter_slow(args.cats_path, {ENGLISH_BLENDS_ID}, verbose=args.verbose)
	print(f'Found {len(blends):,} English blends.')

	blends_by_part: dict[list[str]] = collections.defaultdict(list)
	for page in parsing.etree_helpers.pages_gen(args.pages_path):
		page_id = int(page.findtext('./id'))
		if page_id in blends:
			page_title = page.findtext('./title')
			page_text = page.findtext('./revision/text')
			wikitext = wikitextparser.parse(page_text)

			try:
				lang_section = next(sec for sec in wikitext.get_sections(level=2) if sec.title.strip() == 'English')
			except StopIteration:
				continue
			for subsection in lang_section.get_sections(level=3):
				if subsection.title.strip() == 'Etymology':
					for temp in subsection.templates:
						if temp.normal_name() == 'blend':
							parts = [arg.value for arg in temp.arguments if arg.positional][1:]
							for part in parts:
								if part and not (part.startswith('-') or part.endswith('-')):
									blends_by_part[part].append(page_title)

	print(f'Found {sum(len(blends) for blends in blends_by_part):,} blend components.')

	with open(args.output_path, 'w') as out_file:
		for part, blends in heapq.nlargest(args.output_count, blends_by_part.items(), key=lambda pair: len(pair[1])):
			blends.sort()
			out_file.write(f'==={part}===\n{{{{m-lite|en|{part}}}}} appears in {len(blends)} blends:\n{{{{col|en|sort=0\n')
			for blend in blends:
				out_file.write(f'| {blend}\n')
			out_file.write('}}\n\n')

if __name__ == '__main__':
	main()
