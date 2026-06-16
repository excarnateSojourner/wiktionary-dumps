'''
Find templates that are not yet categorized based on what kind of template they are, so that I can categorize them.
'''

import argparse

import parsing.parse_cats
import parsing.parse_redirects
import parsing.parse_stubs

VERBOSE_FACTOR = 10 ** 6
INSUFFICIENT_CATEGORIES = ['Templates and modules needing documentation']
TEMPLATE_NS_ID = 10

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('stubs_path', help='The path of the CSV file produced by parse_stubs.')
	parser.add_argument('cats_path', help='The path of the CSV file produced by parse_cats.')
	parser.add_argument('redirects_path', help='The path of the CSV file produced by parse_redirects.')
	parser.add_argument('output_path')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Forming initial template list...')
	temp_titles = set()
	for count, stub in enumerate(parsing.parse_stubs.stubs_gen(args.stubs_path)):
		if args.verbose and count % VERBOSE_FACTOR == 0:
			print(f'{count:,}')
		if stub.ns == TEMPLATE_NS_ID and '/' not in stub.title:
			temp_titles.add(stub.title)

	if args.verbose:
		print('Removing redirects...')
	for src_id, src_ns, src_title, dst_id, dst_ns, dst_title in parsing.parse_redirects.redirects_gen(args.redirects_path):
		if src_ns == TEMPLATE_NS_ID:
			temp_titles.discard(src_title)

	if args.verbose:
		print('Removing categorized templates...')
	for cat_id, cat_title, page_id, page_ns, page_title in parsing.parse_cats.cats_gen(args.cats_path):
		if page_ns == TEMPLATE_NS_ID:
			if page_title in temp_titles and cat_title not in INSUFFICIENT_CATEGORIES:
				temp_titles.discard(page_title)

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for title in temp_titles:
			print(f'|{{{{tl|{title}}}}}', file=out_file)

if __name__ == '__main__':
	main()
