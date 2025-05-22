import argparse
import collections

import parsing.parse_cats
import parsing.parse_stubs

def main():
	parser = argparse.ArgumentParser(description='Generate a list of all pages in a set of categories and their descendant categories.')
	parser.add_argument('categories_path', help='Path of the parsed categories file that should be used to enumerate subcategories of explicitly mentioned categories.')
	parser.add_argument('output_path', help='Path of the file to write the IDs of pages in the categories to.')
	parser.add_argument('-c', '--cats', '--categories', required=True, nargs='+', help='Categories to select. These can either all be given as page titles, in which case --stubs-path is required to convert them to page ids, or they can all be given as page IDs (in which case --stubs-path must *not* be given).')
	parser.add_argument('-s', '--stubs-path', help='Path of the CSV file (as produced by parse_stubs.py) containing page IDs and titles. If given, this indicates that the categories to select have been specified using their titles rather than their IDs. Specifying IDs removes the need for this program to perform time-intensive name-to-id translation.')
	parser.add_argument('-u', '--output-ids', action='store_true', help='Indicates that the output should be given as a list of IDs rather than a list of terms.')
	parser.add_argument('-d', '--depth', default=-1, type=int, help='The maximum depth to explore each category\'s descendants. Zero means just immediate children, one means children and grandchildren, etc. A negative value means no limit.')
	parser.add_argument('-a', '--small-ram', action='store_true', help='Indicates that not enough memory (RAM) is available to read all category associations into memory, so they should instead be repeatedly read from disk, even though this is slower. Otherwise this program may use several gigabytes of RAM. (In 2024-01 I ran this with all category associations for the English Wiktionary and it used about 8 GB of RAM.)')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.stubs_path:
		stub_master = parsing.parse_stubs.StubMaster(args.stubs_path)
		select_cats = {stub_master.id(cat, parsing.parse_cats.CAT_NAMESPACE_ID) for cat in args.cats}
	else:
		try:
			select_cats = {int(id_) for id_ in args.cats}
		except ValueError:
			print('Error: It looks like you gave category titles (rather than IDs) but did not give --stubs-path (which is required in such a case).')
			exit()

	if args.small_ram:
		select_pages = deep_cat_filter_slow(args.categories_path, select_cats, return_titles=not args.output_ids, max_depth=args.depth, verbose=args.verbose)
	else:
		cat_master = parsing.parse_cats.CategoryMaster(args.categories_path, verbose=args.verbose)
		select_pages = deep_cat_filter(cat_master, select_cats, return_titles=not args.output_ids, max_depth=args.depth, verbose=args.verbose)

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for page in select_pages:
			print(page, file=out_file)

def deep_cat_filter(
		cat_master: parsing.parse_cats.CategoryMaster,
		select_cats: set[int],
		return_titles: bool = False,
		max_depth: int = -1,
		verbose: bool = False
		) -> set[int] | set[str]:
	if verbose:
		print('Looking for pages and subcategories in selected categories...')
	pages: set[int] | set[str] = set()
	for cat_id in select_cats:
		pages |= cat_master.descendant_pages(cat_id, titles=return_titles)
	return pages

def deep_cat_filter_slow(
		categories_path: str,
		select_cats: set[int],
		return_titles: bool = False,
		max_depth: int = -1,
		verbose: bool = False
		) -> set[int] | set[str]:
	if verbose:
		print('Looking for pages and subcategories in specified categories:')
	# collect subcats to process in the next round
	next_cats = set()
	# avoid reselecting cats we have seen already
	ever_selected_cats = select_cats.copy()
	# collect non-cat pages that are in selected cats
	select_pages = set()

	depth = 0
	while select_cats and (max_depth < 0 or depth <= max_depth):
		if verbose:
			print('', '-' * 10, f'Round {depth}', '-' * 10, sep='\n')
		for cat_link in parsing.parse_cats.cats_gen(categories_path):
			if cat_link.cat_id in select_cats:
				if cat_link.page_ns == parsing.parse_cats.CAT_NAMESPACE_ID:
					if cat_link.page_id not in ever_selected_cats:
						next_cats.add(cat_link.page_id)
						ever_selected_cats.add(cat_link.page_id)
						print(cat_link.page_title)
				elif return_titles:
					select_pages.add(cat_link.page_title)
				else:
					select_pages.add(cat_link.page_id)
		select_cats = next_cats
		next_cats = set()
		depth += 1

	return select_pages

if __name__ == '__main__':
	main()
