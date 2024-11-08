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
	parser.add_argument('pages_path', help='The pages file to read words from. It is recommended that ns.py be used to get just pages in namespaces 0 and 114 (Translation).')
	parser.add_argument('-g', '--ids_path', help='A text file containing page IDs, one per line, which should have their words counted. If given all other pages will be ignored.')
	parser.add_argument('output_path', help='The JSON file in which to write the word counts.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	with open(args.ids_path, encoding='utf-8') as ids_file:
		good_ids = [int(line) for line in ids_file]

	frequencies = collections.Counter()
	for count, page in enumerate(etree_helpers.pages_gen(args.pages_path)):
		try:
			page_id = int(etree_helpers.find_child(page, 'id').text)
			if page_id not in good_ids:
				continue
			raw_text = etree_helpers.find_child(etree_helpers.find_child(page, 'revision'), 'text').text
			if not raw_text:
				continue
			try:
				text = wikitextparser.parse(raw_text).plain_text()
			# Raised by the 24-10-20 dump
			except IndexError:
				continue
			valid_words = []
			for word in text.replace('-', ' ').split():
				word = word.strip(string.punctuation)
				if word and all(ch in VALID_CHARS for ch in word):
					valid_words.append(word)
			frequencies.update(valid_words)
		# Just to catch continues
		finally:
			page.clear()
			if count % VERBOSE_FACTOR == 0:
				print(f'{count:,}')

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		json.dump(frequencies, out_file, indent='\t')

if __name__ == '__main__':
	main()
