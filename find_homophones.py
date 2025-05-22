import argparse
import collections
import re

import wikitextparser

import parsing.etree_helpers

VERBOSE_FACTOR = 10 ** 5
HMP_ALIASES = ['hmp', 'homophone', 'homophones']

def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path')
	parser.add_argument('output_path')
	parser.add_argument('-i', '--target-ids-path')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.target_ids_path:
		with open(args.target_ids_path, encoding='utf-8') as target_ids_file:
			target_ids = {int(line) for line in target_ids_file}

	if args.verbose:
		print('Reading pages:')
	# Maps prons to homophone data
	# Homophone data maps each term with the specified pronunciation to the set of other terms that are already listed as its homophones
	prons_to_titles: dict[str, dict[str, set[str]]] = collections.defaultdict(dict)
	for count, page in enumerate(parsing.etree_helpers.pages_gen(args.pages_path)):
		try:
			if args.target_ids_path:
				page_id = int(parsing.etree_helpers.find_child(page, 'id').text)
				if page_id not in target_ids:
					continue
			title = parsing.etree_helpers.find_child(page, 'title').text
			text = parsing.etree_helpers.find_child(parsing.etree_helpers.find_child(page, 'revision'), 'text').text
			wikitext = wikitextparser.parse(text)
			pron_sections = [sec for sec in wikitext.sections if 3 <= sec.level <= 4 and sec.title.strip() == 'Pronunciation']
			for section in pron_sections:
				existing_hmps: set[str] = set()
				for temp in section.templates:
					if temp.normal_name().casefold() in HMP_ALIASES:
							for arg in temp.arguments[1:]:
								if arg.positional:
									hmp = arg.value
									if '<' in hmp:
										hmp = re.sub(r'<.*?>', '', hmp)
									existing_hmps.add(hmp)
				for temp in section.templates:
					if temp.normal_name().casefold() == 'ipa':
						prons = [arg.value for arg in temp.arguments[1:] if arg.positional]
						for pron in prons:
							if not (pron.startswith('/') and pron.endswith('/')):
								continue
							pron = pron[1:-1]
							if pron.startswith('-') or pron.endswith('-'):
								continue
							prons_to_titles[pron][title] = existing_hmps
		finally:
			page.clear()
			if args.verbose and count % VERBOSE_FACTOR == 0:
				print(f'{count:,}')

	if args.verbose:
		print('Comparing pronunciations...')
	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for pron, titles_to_existing_hmps in prons_to_titles.items():
			all_hmps = set(titles_to_existing_hmps.keys())
			for title, existing_hmps in titles_to_existing_hmps.items():
				good_hmps = all_hmps.copy()
				good_hmps.remove(title)
				good_hmps -= existing_hmps
				if good_hmps:
					print(f'# [[{title}#English|{title}]] ({{{{ic|/{pron}/}}}}): ' + ', '.join(f'[[{hmp}#English|{hmp}]]' for hmp in good_hmps), file=out_file)

if __name__ == '__main__':
	main()
