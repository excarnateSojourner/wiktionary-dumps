'''
Find the most common words for which Wiktionary has too few quotes, so that more can be added.
'''

import argparse
import collections
import json

import wikitextparser

import deep_cat
import parsing.etree_helpers

# If an entry already has this many quotes, that's enough
SATISFACTORY_QUOTE_COUNT = 3
VERBOSE_FACTOR = 10 ** 5

# The page ID of Category:English lemmas
LEMMAS_CAT_ID = 4476265
# The page ID of Category:English multiword terms
MULTIWORD_TERMS_CAT_ID = 7842611
# All templates that create a citations language header
CITATION_TEM_ALIASES = ['citation', 'citations']

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('categories_path')
	parser.add_argument('en_pages_path')
	parser.add_argument('citations_pages_path')
	parser.add_argument('frequencies_path')
	parser.add_argument('output_path')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	lemmas = deep_cat.deep_cat_filter_slow(args.categories_path, {LEMMAS_CAT_ID}, max_depth=0, verbose=args.verbose)

	if args.verbose:
		print('\nReading in word frequencies...\n')
	with open(args.frequencies_path) as frequencies_file:
		word_frequencies = json.load(frequencies_file)

	# Collect entry titles while counting quotes in each entry
	quote_counts: dict[str, int] = collections.Counter()
	# Increment count manually since its used across multiple loops
	count = 0
	if args.verbose:
		print('Searching English entries:')
	for page in parsing.etree_helpers.pages_gen(args.en_pages_path):
		try:
			if int(parsing.etree_helpers.find_child(page, 'id').text) not in lemmas:
				continue
			word = parsing.etree_helpers.find_child(page, 'title').text
			if len(word) == 1:
				continue
			if word.isnumeric():
				continue
			if ' ' in word:
				continue
			'''
			This script is written to use word frequencies that do not distinguish between lowercase and uppercase.
			If we're not careful, this will cause some non-lemma words like "was" to appear in the results:
			1. The loop which searches through entries finds "was", but ignores it since it's not a lemma.
			2. The same loop then finds the surname "Was" and adds "was" as a key to the quote_counts, marking it as a lemma that has no quotes in its entry.
			3. The loop that searches through citations pages then reads through "Citations:was", since "was" is marked as a valid lemma, finds 2 quotes, and adds them to the quotes_count. ("Citations:Was" does not exist.)
			This causes "was" to appear in the results with only 2 quotations, even though the common non-lemma word has plenty of quotations in its entry.
			To prevent this, ignore any alterntive-case forms of very common words.
			'''
			if word != word.casefold() and word_frequencies.get(word.casefold(), 0) > 10 ** 4:
				continue
			entry_text = parsing.etree_helpers.find_child(parsing.etree_helpers.find_child(page, 'revision'), 'text').text or ''
			wikitext = wikitextparser.parse(entry_text)
			en_section = next(sec for sec in wikitext.get_sections(level=2) if sec.title == 'English')
			quote_lists = en_section.get_lists(pattern=r'\#+\*')
			quote_counts[word.casefold()] += sum(len(lis.items) for lis in quote_lists)
		# Protect cleanup from continues
		finally:
			page.clear()
			if args.verbose and count % VERBOSE_FACTOR == 0:
				print(f'{count:,}')
			count += 1

	if args.verbose:
		print(f'Found {len(quote_counts):,} entries for single-word English lemmas with a total of {quote_counts.total():,} quotations.\n')
		print('Searching citations pages:')

	for page in parsing.etree_helpers.pages_gen(args.citations_pages_path):
		if args.verbose and count % VERBOSE_FACTOR == 0:
			print(f'{count:,}')
		count += 1

		word = parsing.etree_helpers.find_child(page, 'title').text.removeprefix('Citations:')
		page_text = parsing.etree_helpers.find_child(parsing.etree_helpers.find_child(page, 'revision'), 'text').text or ''
		wikitext = wikitextparser.parse(page_text)
		# Turn citation templates into headings (as they render on the site) so that we can parse sections
		# But for the text of the heading just use the language code from the template
		for tem in wikitext.templates:
			try:
				if tem.normal_name().casefold() in CITATION_TEM_ALIASES:
					tem.string = f'=={tem.get_arg("1").value}=='
			except wikitextparser._wikitext.DeadIndexError:
				# This template no longer exists, perhaps because it was inside of a previous template that has already been replaced
				pass
		if word.casefold() in quote_counts:
			try:
				en_section = next(sec for sec in wikitext.get_sections(level=2) if sec.title == 'en')
				quote_lists = en_section.get_lists(pattern='\#*\*')
				quote_counts[word.casefold()] += sum(len(lis.items) for lis in quote_lists)
			except StopIteration:
				# A citations page exists, but it's only for other languages
				pass
		page.clear()

	# Assume word frequencies are already sorted to have the most frequent words at the top
	with open(args.output_path, 'w') as out_file:
		for word in word_frequencies.keys():
			if word in quote_counts and quote_counts[word] < SATISFACTORY_QUOTE_COUNT:
				out_file.write(f'# {{{{REEHelp|{word}}}}} ({quote_counts[word]})\n')

if __name__ == '__main__':
	main()
