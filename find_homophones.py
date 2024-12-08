import argparse
import collections

import wikitextparser

import etree_helpers

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
	prons_to_titles: dict[str, tuple[set[str], set[str]]] = collections.defaultdict(lambda: (set(), set()))
	for count, page in enumerate(etree_helpers.pages_gen(args.pages_path)):
		try:
			if args.target_ids_path:
				page_id = int(etree_helpers.find_child(page, 'id').text)
				if page_id not in target_ids:
					continue
			title = etree_helpers.find_child(page, 'title').text
			text = etree_helpers.find_child(etree_helpers.find_child(page, 'revision'), 'text').text
			wikitext = wikitextparser.parse(text)
			pron_sections = [sec for sec in wikitext.sections if 3 <= sec.level <= 4 and sec.title.strip() == 'Pronunciation']
			for section in pron_sections:
				has_hmp = any(True for temp in section.templates if temp.normal_name().casefold() in HMP_ALIASES)
				for temp in section.templates:
					if temp.normal_name().casefold() == 'ipa':
						prons = [arg.value for arg in temp.arguments[1:] if arg.positional]
						for pron in prons:
							if not (pron.startswith('/') and pron.endswith('/')):
								continue
							pron = pron[1:-1]
							if pron.startswith('-') or pron.endswith('-'):
								continue
							prons_to_titles[pron][int(has_hmp)].add(title)
		finally:
			page.clear()
			if args.verbose and count % VERBOSE_FACTOR == 0:
				print(f'{count:,}')

	if args.verbose:
		print('Comparing pronunciations...')
	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for pron, list_pair in prons_to_titles.items():
			titles_without_hmp, titles_with_hmp = list_pair
			if len(titles_without_hmp) > 0 and len(titles_with_hmp) + len(titles_without_hmp) > 1:
				print(f'/{pron}/ already has ' + ', '.join(titles_with_hmp) + ', but it could also have ' + ', '.join(titles_without_hmp), file=out_file)

if __name__ == '__main__':
	main()
