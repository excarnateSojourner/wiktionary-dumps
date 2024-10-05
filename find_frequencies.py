import argparse
import collections
import json
import string

import wikitextparser

import etree_helpers

VERBOSE_FACTOR = 10 ** 4
VALID_CHARS = string.ascii_letters + string.digits

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path')
	parser.add_argument('output_path')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	frequencies = collections.defaultdict(int)
	for count, page in enumerate(etree_helpers.pages_gen(args.pages_path)):
		if count % VERBOSE_FACTOR == 0:
			print(f'{count:,}')
		text = etree_helpers.find_child(etree_helpers.find_child(page, 'revision'), 'text').text
		if not text:
			continue
		text = wikitextparser.parse(text).plain_text()
		for word in text.replace('-', ' ').split():
			word = word.strip(punctuation)
			if word and all(ch in VALID_CHARS for ch in word):
				frequencies[word] += 1

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		json.dump(frequencies, out_file, indent='\t')

if __name__ == '__main__':
	main()
