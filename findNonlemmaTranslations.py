import argparse
import re
import sys
import wikitextparser
import xml.dom.pulldom

import parseCats
import pulldomHelpers

VERBOSE_FACTOR = 10 ** 4
# the id of Category:English non-lemma forms
NON_LEMMA_CAT_ID = 4482934
LEMMA_CAT_ID = 4476265

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path', help='Path of the pages file to search through.')
	parser.add_argument('categories_path', help='Path of the parsed categories file that should be used to enumerate all English non-lemmas.')
	parser.add_argument('output_path', help='Path of the file to write non-lemma terms that have translations to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Finding non-lemma terms...')
	nonLemmaIds = set()
	lemmaIds = set()
	for data in parseCats.catsGen(args.categories_path):
		if data.catId == NON_LEMMA_CAT_ID:
			nonLemmaIds.add(data.pageId)
		elif data.catId == LEMMA_CAT_ID:
			lemmaIds.add(data.pageId)
	ids = nonLemmaIds - lemmaIds
	if args.verbose:
		print(f'Found {len(ids)} non-lemmas.')

	doc = xml.dom.pulldom.parse(args.pages_path)
	count = 0
	print('Non-lemmas with translations:')
	with open(args.output_path, 'w', encoding='utf-8') as outFile:
		for event, node in doc:
			if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'page':
				doc.expandNode(node)
				if int(pulldomHelpers.getDescendantContent(node, 'id')) in ids:
					ast = wikitextparser.parse(pulldomHelpers.getDescendantContent(node, 'text'))
					try:
						englishSection = next(s for s in ast.get_sections(level=2) if s.title.strip() == 'English')
						if '{{trans-top|' in englishSection:
							print(pulldomHelpers.getDescendantContent(node, 'title'), file=outFile)
					except StopIteration:
						# term has no English definitions
						pass
					if args.verbose and count % VERBOSE_FACTOR == 0:
						print(count)
					count += 1

if __name__ == '__main__':
	main()
