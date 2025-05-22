'''
I want to play the Android game Lexica (https://github.com/lexica/lexica) with IPA symbols for the pronunciation of English words, rather than English words themselves.
Since Lexica already supports multiple languages, it appears all I need is a list of pronunciations to consider valid.
This script is to generate such a list for my Canadian accent of English.
'''

import argparse
import collections.abc
import re
import xml.etree.ElementTree as xet

import wikitextparser

import parsing.etree_helpers

VERBOSE_FACTOR = 10 ** 5

# I've chosen to hardcode these accents rather than making them command line arguments only because I don't want to bother create appropriate replacements for other accents that I don't plan to use
TARGET_ACCENTS = {'Canada', 'CA', 'General American', 'GA', 'GenAm', 'United States', 'US'}
MONOPHONEMES = 'iuæɑɔəɚɛɜɪʊ' + 'bdfhjklmnpstvwzðŋɡɹɾʃʒθ'
DIPHONEMES = {'aɪ', 'aʊ', 'eɪ', 'oʊ', 'ɔɪ'}
ACCENT_REPLACEMENTS = {'ʌ': 'ə', 'əʊ': 'oʊ', 'ɒ': 'ɑ', 'ɝ': 'ɚ', 'ɪə': 'ɪɚ', '(ɹ)': 'ɹ'}
# Based on https://youtu.be/gtnlGH055TA but adjusted to match a North American accent
LINDSEY_REPLACEMENTS = {'i': 'ij', 'u': 'uw', 'eɪ': 'ej', 'ɔɪ': 'ɔj', 'oʊ': 'ow', 'aɪ': 'aj', 'aʊ': 'aw'}
# The only ASCII char in NON_RHYME_CHARS is a space, even though others may appear to be ASCII
EXTRANEOUS_CHARS = {
	'.', # Full stop for syllable boundaries
	' ', # Space for word boundaries
	'(', ')',
	'\u02C8', # Primary stress
	'\u02CC', # Secondary stress
	'\u0306', # Extra-short
	'\u02D1', # Half-long
	'\u02D0', # Long
	'\u032F', # Non-syllabic
	'\u0329', # Syllablic
	'\u0361', # Affricate breve
}
UNORDERED_LIST_PATTERN = r'\*'

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path', help='Path of the pages file containing the text of entries in which to find pronunciations.')
	parser.add_argument('pronunciation_path', help='Path of the text file in which to write the valid pronunciations.')
	parser.add_argument('full_output_path', help='Path of the file in which to list the title of each entry containing pronunciations, with the pronunciations found in that entry. This is useful when determining what entry a valid pronunciation came from, or why a pronunciation you thought would appear did not.')
	parser.add_argument('-i', '--ids-path', help='Path of a file containing the IDs of entries that should be parsed to find pronunciations. All other pages are ignored. This can be used in with the output of deep_cat or find_terms to avoid parsing pages that do not have any English pronunciations.')
	parser.add_argument('-l', '--lindsey-glides', action='store_true', help='Automatically add glides to create more accurate transcriptions, as described in Dr Geoff Lindsey\'s video here: https://youtu.be/gtnlGH055TA')
	parser.add_argument('-w', '--warnings', action='store_true')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.ids_path:
		with open(args.ids_path, encoding='utf-8') as ids_file:
			target_ids = {int(line) for line in ids_file}
	if args.lindsey_glides:
		LINDSEY_PATTERN = '|'.join(old for old in LINDSEY_REPLACEMENTS)
		LINDSEY_SUB_FUNC: collections.abc.Callable[[re.Match], str] = lambda old: LINDSEY_REPLACEMENTS[old[0]]

	prons: set[str] = set()
	with open(args.full_output_path, 'w', encoding='utf-8') as full_output_file:
		for count, page in enumerate(parsing.etree_helpers.pages_gen(args.input_path)):
			try:
				if args.ids_path:
					page_id = int(parsing.etree_helpers.find_child(page, 'id').text)
					if page_id not in target_ids:
						continue
				page_title = parsing.etree_helpers.find_child(page, 'title').text
				text = parsing.etree_helpers.find_child(parsing.etree_helpers.find_child(page, 'revision'), 'text').text
				wikitext = wikitextparser.parse(text)
				pron_sections = (sec for sec in wikitext.sections if 3 <= sec.level <= 4 and sec.title == 'Pronunciation')
				entry_prons: set[str] = set()
				for section in pron_sections:
					pron_lists = section.get_lists(pattern=UNORDERED_LIST_PATTERN)
					for lis in pron_lists:
						section_prons = prons_from_wikilist(lis,word=page_title if args.warnings else None, accents=TARGET_ACCENTS)
						if args.lindsey_glides:
							section_lindsey_prons: set[str] = set()
							for pron in section_prons:
								section_lindsey_prons.add(re.sub(LINDSEY_PATTERN, LINDSEY_SUB_FUNC, pron))
							section_prons = section_lindsey_prons
						# Lexica does not permit very short or long words
						section_prons = {pron for pron in section_prons if 3 <= len(pron) <= 9}
						entry_prons |= section_prons
				if entry_prons:
					print(f'{page_title}: {", ".join(entry_prons)}', file=full_output_file)
					prons |= entry_prons
			finally:
				page.clear()
				if args.verbose and count % VERBOSE_FACTOR == 0:
					print(f'{count:,}')

	with open(args.pronunciation_path, 'w', encoding='utf-8') as pronunciation_file:
		sorted_prons = sorted(prons)
		for pron in sorted_prons:
			print(pron, file=pronunciation_file)

def prons_from_wikilist(wikilist: wikitextparser.WikiList, word: str | None = None, accents: collections.abc.Container[str] | None = None) -> set[str]:
	'''
	Extracts all the pronunciations in the chosen accents (if specified) from a WikiList.
	'''
	target_accents = accents if accents else []
	prons = set()

	for count, item in enumerate(wikilist.items):
		item = wikitextparser.parse(item)
		for temp in item.templates:
			match temp.normal_name().casefold():
				case 'a':
					found_accents = (arg.value for arg in temp.arguments[1:] if arg.positional)
					if not any(accent in target_accents for accent in found_accents) and any(not accent.islower() for accent in found_accents):
						# Skip the rest of the item (and any subitems)
						break
				case 'enpr':
					if target_accents:
						accent_arg = temp.get_arg('a')
						if accent_arg:
							found_accents = accent_arg.value.split(',')
							if found_accents and any(not accent.islower() for accent in found_accents) and not any(accent in target_accents for accent in found_accents):
								break
				case 'ipa':
					if target_accents:
						accent_arg = temp.get_arg('a')
						if accent_arg:
							found_accents = accent_arg.value.split(',')
							if found_accents and any(not accent.islower() for accent in found_accents) and not any(accent in target_accents for accent in found_accents):
								continue

					args = (arg.value for arg in temp.arguments[1:] if arg.positional)
					for arg in args:
						if not (arg.startswith('/') and arg.endswith('/')):
							if not (arg.startswith('[') and arg.endswith(']')):
								if word:
									print(f'Warning: Skipping pronunciation of {word}: {arg}.')
							continue
						arg = arg.removeprefix('/').removesuffix('/')
						if arg.startswith('-') or arg.endswith('-') or not arg:
							continue
						for old, new in ACCENT_REPLACEMENTS.items():
							arg = arg.replace(old, new)

						for protopron in expand_parens(arg):
							pron = []
							while protopron:
								if any(protopron.startswith(pho) for pho in DIPHONEMES):
									pron.append(protopron[:2])
									protopron = protopron[2:]
								elif protopron[0] in MONOPHONEMES:
									pron.append(protopron[0])
									protopron = protopron[1:]
								elif protopron[0] in EXTRANEOUS_CHARS:
									protopron = protopron[1:]
								else:
									if word:
										fragment = protopron[:1]
										decoded = fragment.encode("unicode_escape").decode()
										print(f'Warning: Rejecting pronunciation of "{word}" containing "{fragment}"' + ('.' if fragment == decoded else f'({decoded}).'))
									break
							# If all chars were valid
							if not protopron:
								prons.add(''.join(pron))

		# A for-else? In actual code? Wild.
		# If all accents were valid
		else:
			for sublist in wikilist.sublists(count, pattern=UNORDERED_LIST_PATTERN):
				prons |= prons_from_wikilist(sublist)

	return prons

def expand_parens(pron: str) -> list:
	'''Return a list of strings containing all combinations of including and excluding each of the parentheticals in pron.'''
	parts = re.split(r'\(([^()])\)', pron, maxsplit=1)
	# If no parentheticals
	if len(parts) < 3:
		return [pron]
	# If parenthetical found
	else:
		combs = []
		for comb in expand_parens(parts[2]):
			combs.append(parts[0] + comb)
			combs.append(parts[0] + parts[1] + comb)
		return combs

if __name__ == '__main__':
	main()
