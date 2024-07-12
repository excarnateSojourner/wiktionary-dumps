import argparse
import collections.abc
import re
import xml.etree.ElementTree as xet

import wikitextparser

import etree_helpers

VERBOSE_FACTOR = 10 ** 4

TARGET_ACCENTS = {'Canada', 'CA', 'General American', 'GA', 'GenAm', 'United States', 'US'}
REPLACEMENTS = {'əʊ': 'oʊ', 'ɒ': 'ɑ', 'ɝ': 'ɚ', 'ɪə': 'ɪɚ', '(ɹ)': 'ɹ'}
MONOPHONEMES = 'iuæɑɔəɚɛɜɪʊʌ' + 'bdfhjklmnpstvwzðŋɡɹɾʃʒθ'
DIPHONEMES = {'aɪ', 'aʊ', 'eɪ', 'oʊ', 'ɔɪ'}
# the only ASCII char in NON_RHYME_CHARS is a space, even though others may appear to be ASCII
EXTRANEOUS_CHARS = {
	'.', # full stop for syllable boundaries
	' ', # space for word boundaries
	'(', ')',
	'\u02C8', # primary stress
	'\u02CC', # secondary stress
	'\u0306', # extra-short
	'\u02D1', # half-long
	'\u02D0', # long
	'\u032F', # non-syllabic
	'\u0329', # syllablic
	'\u0361', # affricate breve
}
UNORDERED_LIST_PATTERN = r'\*'

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path')
	parser.add_argument('pronunciation_path')
	parser.add_argument('full_output_path')
	parser.add_argument('-w', '--warnings', action='store_true')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	with open(args.pronunciation_path, 'w', encoding='utf-8') as pronunciation_file:
		with open(args.full_output_path, 'w', encoding='utf-8') as full_output_file:
			for i, page in enumerate(etree_helpers.pages_gen(args.input_path)):
				if args.verbose and i % VERBOSE_FACTOR == 0:
					print(i)

				page_title = etree_helpers.find_child(page, 'title').text
				text = etree_helpers.find_child(etree_helpers.find_child(page, 'revision'), 'text').text
				wikitext = wikitextparser.parse(text)
				pron_sections = (sec for sec in wikitext.sections if 3 <= sec.level <= 4 and sec.title == 'Pronunciation')
				prons = set()
				for section in pron_sections:
					pron_lists = section.get_lists(pattern=UNORDERED_LIST_PATTERN)
					for lis in pron_lists:
						prons.update(prons_from_wikilist(lis,word=page_title if args.warnings else None, accents=TARGET_ACCENTS))
					if prons:
						pronunciation_file.write(f'{"\n".join(prons)}\n')
						full_output_file.write(f'{page_title}: {", ".join(prons)}\n')

def prons_from_wikilist(wikilist: wikitextparser.WikiList, word: str | None = None, accents: collections.abc.Container[str] | None = None) -> set[str]:
	'''
	Extracts all the pronunciations in the chosen accents (if specified) from a WikiList.
	If accents is not None it can be any container, but a set is recommended for efficiency.
	'''
	target_accents = accents
	prons = set()

	for i, item in enumerate(wikilist.items):
		item = wikitextparser.parse(item)
		for temp in item.templates:
			match temp.normal_name().casefold():
				case 'a':
					found_accents = (arg.value for arg in temp.arguments[1:] if arg.positional)
					if target_accents and not any(accent in target_accents for accent in found_accents) and any(not accent.islower() for accent in found_accents):
						# skip the rest of the item (and any subitems)
						break
				case 'enpr':
					if target_accents:
						accent_arg = temp.get_arg('a')
						if accent_arg:
							found_accent = accent_arg.value
							if found_accent and not found_accent.islower() and found_accent not in target_accents:
								break
				case 'ipa':
					if target_accents:
						accent_arg = temp.get_arg('a')
						if accent_arg:
							found_accent = accent_arg.value
							if found_accent and not found_accent.islower() and found_accent not in target_accents:
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
						for old, new in REPLACEMENTS.items():
							arg = arg.replace(old, new)

						for protopron in expand_parens(arg):
							pron = []
							while protopron:
								if any(protopron.startswith(pho) for pho in DIPHONEMES):
									pron.append(protopron[:2])
									protopron = protopron[2:]
								elif protopron[0] in MONOPHONEMES:
									pron.append(protopron[:1])
									protopron = protopron[1:]
								elif protopron[0] in EXTRANEOUS_CHARS:
									protopron = protopron[1:]
								else:
									if word:
										fragment = protopron[:1]
										print(f'Warning: Rejecting pronunciation of "{word}" containing "{fragment}" ({fragment.encode("unicode_escape").decode()}).')
									break
							# If all chars were valid
							if not protopron:
								prons.add(''.join(pron))

		# if all accents were valid
		else:
			for sublist in wikilist.sublists(i, pattern=UNORDERED_LIST_PATTERN):
				prons |= prons_from_wikilist(sublist)

	return prons

def expand_parens(pron):
	'''Return a list of strings containing all combinations of including and excluding each of the parentheticals in pron.'''
	parts = re.split(r'\(([^()])\)', pron, maxsplit=1)
	# if no parentheticals
	if len(parts) < 3:
		return [pron]
	# if parenthetical found
	else:
		combs = []
		for comb in expand_parens(parts[2]):
			combs.append(parts[0] + comb)
			combs.append(parts[0] + parts[1] + comb)
		return combs

if __name__ == '__main__':
	main()
