import argparse
import collections
import xml.etree.ElementTree as xet

import wikitextparser

import etree_helpers

VERBOSE_FACTOR = 10 ** 4

MONOPHONEMES = 'iuæɑɒɔəɚɛɜɝɪʊʌ' + 'bdfhjklmnpstvwzðŋɡɹɾʃʒθ'
DIPHONEMES = {'aɪ', 'aʊ', 'eɪ', 'oʊ', 'ɔɪ', 'əʊ', 'ɛə', 'ɪə', 'ʊə'}
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
	parser.add_argument('-a', '--accents', nargs='+', help='Accents to consider valid. If omitted, all accents are considered valid.')
	parser.add_argument('-w', '--warnings', action='store_true')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()
	target_accents = set(args.accents) if args.accents else None

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
						prons.update(prons_from_wikilist(lis,word=page_title if args.warnings else None, accents=target_accents))
					if prons:
						pronunciation_file.write(f'{"\n".join(prons)}\n')
						full_output_file.write(f'{page_title}: {", ".join(prons)}\n')

def prons_from_wikilist(wikilist: wikitextparser.WikiList, word: str | None = None, accents: set[str] | None = None) -> set[str]:
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
					found_accent = temp.get_arg('a')
					if found_accent and not found_accent.islower() and found_accent not in target_accents:
						break
				case 'ipa':
					found_accent = temp.get_arg('a')
					if found_accent and not found_accent.islower() and found_accent not in target_accents:
						continue
					for arg in (arg.value for arg in temp.arguments[1:] if arg.positional):
						if not (arg.startswith('/') and arg.endswith('/')):
							if not (arg.startswith('[') and arg.endswith(']')):
								if word:
									print(f'Warning: Skipping pronunciation of {word}: {arg}.')
							continue
						arg = arg.removeprefix('/').removesuffix('/')
						if arg.startswith('-') or arg.endswith('-') or not arg:
							continue
						pron = []
						while arg:
							if any(arg.startswith(pho) for pho in DIPHONEMES):
								pron.append(arg[:2])
								arg = arg[2:]
							elif arg[0] in MONOPHONEMES:
								pron.append(arg[:1])
								arg = arg[1:]
							elif arg[0] in EXTRANEOUS_CHARS:
								arg = arg[1:]
							else:
								if word:
									fragment = arg[:1]
									print(f'Warning: Rejecting pronunciation of "{word}" containing "{fragment}" ({fragment.encode("unicode_escape").decode()}).')
								break
						if not arg:
							prons.add(''.join(pron))

		# if all accents were valid
		else:
			for sublist in wikilist.sublists(i, pattern=UNORDERED_LIST_PATTERN):
				prons |= prons_from_wikilist(sublist)

	return prons

if __name__ == '__main__':
	main()
