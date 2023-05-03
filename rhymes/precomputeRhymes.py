import argparse
import collections
import importlib
import itertools
import re
import subprocess
import xml.dom
import xml.dom.pulldom

import wiktionary.deepCatFilter
import wiktionary.pulldomHelpers

# English 2-syllable words
INCLUDE_CATS = {5834597}
# English prefix forms, English suffix forms, English affixes, English circumfixes, English clitics, English infixes, English interfixes, English prefixes, English suffixes
EXCLUDE_CATS = {52195, 78364, 93234, 261835, 600201, 1600728, 4553094, 6334781, 8734636}
MAIN_VERBOSE_FACTOR = 10 ** 3
SKIPPING_VERBOSE_FACTOR = 10 ** 4

VOWELS = 'aeiouæɑɒɔəɚɛɜɝɪʊʌ'
# the only ASCII char in NON_RHYME_CHARS is a space, even though others may appear to be ASCII
NON_RHYME_CHARS = '.ˈˌ ͡'
CONSONANTS = 'bdfhkjlmnpstvwzðŋɡɹʃʒʔθ'
STANDARD_CHARS = '()ː' + CONSONANTS + VOWELS + NON_RHYME_CHARS
STANDARD_PRON = r'/[' + STANDARD_CHARS + r']+/'
PRON_TO_RHYME = r'[' + STANDARD_CHARS + ']*?(\(?[' + VOWELS + r'][' + STANDARD_CHARS + ']*)/$'

def main():

	parser = argparse.ArgumentParser()
	parser.add_argument('-p', '--pages-path', required=True, help='The path of an XML file containing MediaWiki page text to search through.')
	parser.add_argument('-c', '--categories-path', help='The path of a text file containing, on each line, a category name and the title of a page in that category (separated by a comma).')
	parser.add_argument('-r', '--prons-path', required=True, help='The path of a text file containing all English pronunciations.')
	parser.add_argument('-o', '--output-path', required=True, help='The path of a MediaWiki file to write the words lacking rhymes to. They will be automatically formatted as links listed in five columns. This file will be created if it does not exist, and *overwritten without warning* if it does.')
	parser.add_argument('-w', '--word-cache-path', help='The path of a text file in which to cache the contents of categories relevant to finding words without rhymes. (It will be created if it does not exist.)')
	parser.add_argument('-f', '--refresh-cache', action='store_true', help='Force a refresh of the cache, even if it appears to be up to date.')
	parser.add_argument('-i', '--start-id', type=int, help='Skip over all pages with ID less than this.')
	parser.add_argument('-v', '--verbose', action='store_true', help='Print the words lacking rhymes to stdout as they are found.')
	parser.add_argument('-e', '--example-count', default=4, type=int, help='Specify the number of example words to give that probably rhyme with the target word. Defaults to 4.')
	args = parser.parse_args()
	if not args.categories_path and not args.word_cache_path:
		raise ValueError('At least one of --category-path (-c) and --word-cache-path (-w) must be provided.')

	words = findRhymelessWords(args)

	with open(args.output_path, 'w', encoding='utf-8') as outFile:
		print('{|class="wikitable"', '!Word', '!Suggested template', '!Rhymes', '!Rhyming pronunciation count', '!Rhyming pronunciation examples', '|-', sep='\n', file=outFile)
		for word, prons in words:
			rhymeSiblings = {}
			try:
				rhymes = pronsToRhymes(prons)
			except ValueError:
				writeTableRow(word, {}, outFile)
				continue
			for rhyme in rhymes:
				siblings = findSiblings(rhyme, args)
				if len(siblings) > 1:
					rhymeSiblings[rhyme] = (len(siblings), siblings[:args.example_count])
			if rhymeSiblings:
				writeTableRow(word, rhymeSiblings, outFile)
		print('|}', file=outFile)

def findRhymelessWords(args):
	catedWords = findCategorizedWords(args)
	doc = xml.dom.pulldom.parse(args.pages_path)
	for event, node in doc:
		if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'page':
			doc.expandNode(node)
			pageId = int(wiktionary.pulldomHelpers.getDescendantContent(node, 'id'))
			if args.start_id and pageId < args.start_id:
				if args.verbose and pageId % SKIPPING_VERBOSE_FACTOR == 0:
					print(f'Skipping ID {pageId}...')
				continue
			elif args.verbose and pageId % MAIN_VERBOSE_FACTOR == 0:
				print(f'Processing ID {pageId}...')
			title = wiktionary.pulldomHelpers.getDescendantContent(node, 'title')
			text = wiktionary.pulldomHelpers.getDescendantContent(node, 'text')
			if pageId in catedWords and ('{{IPA|en|' in text or '{{ipa|en|' in text) and not ('{{rhymes|en|' in text or '{{rhyme|en|' in text):
				prons = []
				for pronSet in re.findall('{{IPA\|en\|(.*?)}}', text, flags=re.IGNORECASE):
					prons.extend(pronSet.split('|'))
				yield (title, prons)

def findSiblings(rhyme, args):
	process = subprocess.run(['grep', '-P', f'(ˈ|/[ˈ{CONSONANTS}]*){rhyme}/', args.prons_path], capture_output=True)
	return process.stdout.decode().splitlines()

def writeTableRow(word, rhymeSiblings, outFile):
	def printRow(*strs, **kwargs):
		print(*(f'|{s}' for s in strs), sep='\n', file=outFile, **kwargs)

	if rhymeSiblings:
		if len(rhymeSiblings) == 1:
			printRow(f'{{{{l|en|{word}}}}}')
			printRow('<code><nowiki>* {{rhymes|en|' + '|'.join(rhymeSiblings) + '|s=2}}</nowiki></code>')
		else:
			rowspan = f'rowspan="{len(rhymeSiblings)}"|'
			printRow(f'{rowspan}{{{{l|en|{word}}}}}')
			printRow(rowspan + '<code><nowiki>* {{rhymes|en|' + '|'.join(rhymeSiblings) + '|s=2}}</nowiki></code>')
		for rhyme, siblings in rhymeSiblings.items():
			printRow('{{IPAchar|/-' + rhyme + '/}}')
			printRow(siblings[0])
			printRow('; '.join('{{IPAchar|' + example + '}}' for example in siblings[1]))
			printRow('-')
	else:
		printRow(f'{{{{l|en|{word}}}}}')
		printRow('\n|\n|\n|\n|-')

def pronsToRhymes (prons):
	'''Extracts the corresponding rhyme for each of the IPA pronunciations in prons, and:
	* combines rhymes that differ only in their inclusion of an 'ɹ';
	* expands rhymes containing non-(ɹ) parentheticals into multiple rhymes;
	* deduplicates the rhymes.'''
	phonemicProns = []
	for i, pron in enumerate(prons):
		if not (pron.startswith('[') or pron.endswith(']')):
			if re.fullmatch(STANDARD_PRON, pron):
				pron = pron.replace('ɚ', 'ə(ɹ)')
				pron = pron.replace('ɝ', 'ɜ(ɹ)')
				phonemicProns.append(pron)

	rhymes = []
	for pron in phonemicProns:
		# find primary stress indicated
		try:
			rhymes.append(re.search('ˈ' + PRON_TO_RHYME, pron)[1])
		# primary stress not indicated
		except TypeError:
			pass

	removeNonRhymeChars = str.maketrans('', '', NON_RHYME_CHARS)
	rhymes = [rhyme.translate(removeNonRhymeChars) for rhyme in rhymes]

	# deduplicate
	rhymes = list(dict.fromkeys(rhymes))

	rhymes = combineOnR(rhymes)
	rhymes = itertools.chain.from_iterable(expandParens(rhyme) for rhyme in rhymes)

	# deduplicate
	return list(dict.fromkeys(rhymes))

def combineOnR (rhymes):
	'''Takes a list of rhymes and properly combines rhymes that differ only in their inclusion of 'ɹ' (and possibly a long vowel symbol). If any rhyme has more than one instance of 'ɹ', it is a ValueError.'''
	combined = []

	def addWithAndWithoutLongVowel(before, after):
		combs.append(before + after)
		if before.endswith('ː'):
			combs.append(before.rstrip('ː') + after)
		else:
			combs.append(before + 'ː' + after)

	def findCombMatch(rhyme0, combs):
		for i, rhyme1 in enumerate(rhymes):
			if rhyme1:
				for comb in combs:
					if rhyme1 == comb:
						rhymes[i] = None
						before, after = re.split('\(?ɹ\)?', rhyme0)
						# if rhyme0 or comb has a long vowel symbol before the 'ɹ'
						if before.endswith('ː') or re.search('ː\(?ɹ', comb):
							return before + 'ː(ɹ)' + after
						else:
							return before + '(ɹ)' + after

	remaining = rhymes.copy()
	for rhyme0 in rhymes:
		if rhyme0:
			# if rhyme0 contains one 'ɹ'
			if (rCount := rhyme0.count('ɹ')) == 1:
				before, after = rhyme0.split('ɹ', maxsplit=1)
				combs = []
				if before.endswith('(') and after.startswith(')'):
					before = before[:-1]
					after = after[1:]
					addWithAndWithoutLongVowel(before, 'ɹ' + after)
				else:
					addWithAndWithoutLongVowel(before, '(ɹ)' + after)
				addWithAndWithoutLongVowel(before, after)
				melded = findCombMatch(rhyme0, combs)
				combined.append(melded if melded else rhyme0)
			# rhyme0 contains more than one 'ɹ'
			elif rCount > 1:
				raise ValueError('One of the rhymes includes more than one instance of /ɹ/.')

	return combined + [rhyme for rhyme in rhymes if rhyme and 'ɹ' not in rhyme]

def expandParens (s):
	'''Return a list of strings containing all combinations of including and excluding each of the parentheticals in s.'''
	parts = re.split(r'\(([^ɹ])\)', s, maxsplit=1)
	# if no parentheticals
	if len(parts) < 3:
		return [s]
	# if parenthetical found
	else:
		combs = []
		for comb in expandParens(parts[2]):
			combs.append(parts[0] + comb)
			combs.append(parts[0] + parts[1] + comb)
		return combs

def findCategorizedWords(args):
	if args.word_cache_path and not args.refresh_cache:
		try:
			with open(args.word_cache_path, encoding='utf-8') as cacheFile:
				return set(int(line[:-1]) for line in cacheFile)
		except FileNotFoundError:
			pass

	# cache is missing or outdated, so we need to refresh it
	includeWords = set()
	excludeWords = set()
	for data in wiktionary.deepCatFilter.catsGen(args.categories_path):
		if data.catId in INCLUDE_CATS:
			includeWords.add(data.pageId)
		elif data.catId in EXCLUDE_CATS:
			excludeWords.add(data.pageId)
	words = includeWords - excludeWords

	if args.word_cache_path:
		with open(args.word_cache_path, 'w', encoding='utf-8') as cacheFile:
			for word in words:
				print(word, file=cacheFile)

	return words

if __name__ == '__main__':
	main()
