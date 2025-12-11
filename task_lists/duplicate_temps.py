import argparse
import collections

import parsing.etree_helpers

VERBOSE_FACTOR = 10 ** 5

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path')
	parser.add_argument('output_path')
	args = parser.parse_args()

	hashes = collections.defaultdict(list)
	for page_count, page in enumerate(parsing.etree_helpers.pages_gen(args.pages_path)):
		title = parsing.etree_helpers.find_child(page, 'title').text
		if not title.endswith('/documentation'):
			text = parsing.etree_helpers.find_child(parsing.etree_helpers.find_child(page, 'revision'), 'text').text
			hashes[hash(text)].append(title)
		if page_count % VERBOSE_FACTOR == 0:
			print(f'{page_count:,}')

	with open(args.output_path, 'w') as out_file:
		for hash_, titles in hashes.items():
			if len(titles) > 1:
				out_file.write('# ' + ', '.join(f'[[{title}]]' for title in titles) + '\n')

if __name__ == '__main__':
	main()
