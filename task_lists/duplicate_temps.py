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
		if page_count % VERBOSE_FACTOR == 0:
			print(f'{page_count:,}')

		title = page.findtext('./title')
		if not title.endswith('/documentation'):
			text = page.findtext('./revision/text')
			if text and not text.casefold().startswith('#redirect'):
				hashes[hash(text)].append(title)

	with open(args.output_path, 'w') as out_file:
		for hash_, titles in hashes.items():
			if len(titles) > 1:
				out_file.write('# ' + ', '.join(f'[[{title}]]' for title in titles) + '\n')

if __name__ == '__main__':
	main()
