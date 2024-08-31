import argparse

import parse_cats
import parse_redirects
import parse_stubs

INSUFFICIENT_CATEGORIES = ['Templates and modules needing documentation']
TEMPLATE_NS = 10
TEMPLATE_PREFIX = 'Template:'

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('stubs_path', help='The path of the CSV file produced by parse_stubs.')
	parser.add_argument('cats_path', help='The path of the CSV file produced by parse_cats.')
	parser.add_argument('redirects_path', help='The path of the CSV file produced by parse_redirects.')
	parser.add_argument('output_path')
	args = parser.parse_args()

	temp_titles = {title.removeprefix(TEMPLATE_PREFIX) for id_, ns, title in parse_stubs.stubs_gen(args.stubs_path) if ns == TEMPLATE_NS and '/' not in title}

	for src_id, src_title, dst_id, dst_title in parse_redirects.redirects_gen(args.redirects_path):
		if src_title.startswith(TEMPLATE_PREFIX):
			temp_titles.discard(src_title.removeprefix(TEMPLATE_PREFIX))

	for cat_id, cat_title, page_id, page_title in parse_cats.cats_gen(args.cats_path):
		if page_title.startswith(TEMPLATE_PREFIX):
			temp_title = page_title.removeprefix(TEMPLATE_PREFIX)
			if temp_title in temp_titles and cat_title not in INSUFFICIENT_CATEGORIES:
				temp_titles.discard(temp_title)

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for title in temp_titles:
			print(f'|{{{{tl|{title}}}}}', file=out_file)

if __name__ == '__main__':
	main()
