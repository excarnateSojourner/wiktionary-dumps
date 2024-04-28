'''
See https://en.wiktionary.org/wiki/User:ExcarnateSojournerBot/Past_projects#Replace_curly_quotes_in_Taos_terms

This script is no longer used.
'''

import argparse
import re

import pulldom_helpers

VERBOSITY_FACTOR = 10 ** 4
QUOTE = '\N{RIGHT SINGLE QUOTATION MARK}'
parser = argparse.ArgumentParser()
parser.add_argument('pages_path')
parser.add_argument('output_path')
parser.add_argument('-v', '--verbose', action='store_true')
args = parser.parse_args()

with open(args.output_path, 'w', errors='ignore') as out_file:
	for page_count, page in enumerate(pulldom_helpers.get_page_descendant_text(args.pages_path, ['title', 'text'])):
		for line_count, line in enumerate(page['text'].splitlines()):
			if '|twf|' in line:
				match = re.search(r'\{\{[^}]+?\|twf\|[^}]*?' + QUOTE + '.*?\}\}', line)
				if match:
					print(page["title"], file=out_file)
		if args.verbose and page_count % VERBOSITY_FACTOR == 0:
			print(page_count)
