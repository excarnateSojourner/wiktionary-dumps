import argparse
import collections
import re

import wikitextparser

import parsing.etree_helpers

VERBOSE_FACTOR = 10 ** 5

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path')
	parser.add_argument('output_path')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	headings = collections.Counter()
	for count, page in enumerate(parsing.etree_helpers.pages_gen(args.pages_path)):
		if args.verbose and count % VERBOSE_FACTOR == 0:
			print(f'{count:,}')
		wikitext = wikitextparser.parse(page.findtext('./revision/text'))
		for section in wikitext.get_sections(level=3):
			if re.search(r' \d+$', section.title):
				headings.update([sub.title.casefold() for sub in section.get_sections(level=4)])
			else:
				headings[section.title.casefold()] += 1

	with open(args.output_path, 'w') as out_file:
		for heading, count in headings.most_common():
			out_file.write(f'{heading.capitalize()}: {count}\n')

if __name__ == '__main__':
	main()
