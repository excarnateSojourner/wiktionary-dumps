import argparse
import pulldomHelpers
import xml.dom.pulldom

CAT_PREFIX = 'Category:'

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('categories_path', help='Path of the parsed categories file that should be used to enumerate subcategories of explicitly mentioned categories.')
	parser.add_argument('output_path', help='Path of the file to ')
	parser.add_argument('-i', '--include', required=True, nargs='+', default=[], help='Categories to include.')
	parser.add_argument('-e', '--exclude', nargs='+', default=[], help='Categories to exclude (overriding includes).')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	cats = catFilter(args.categories_path, args.include, args.exclude, args.verbose)
	with open(args.output_path, 'w') as outFile:
		# each of the ids is already suffixed with a newline
		outFile.writelines(f'{pageTitle}\n' for pageTitle in cats)

def catFilter(categories_path, include, exclude=None, verbose=False):
	# cats being processed in this round
	includeCats = set(include)
	excludeCats = set(exclude) if exclude else set()
	# collect subcats to process in the next round
	nextIncludeCats = set()
	nextExcludeCats = set()
	# collect non-cat pages in cats
	includePages = set()
	excludePages = set()

	while includeCats or excludeCats:
		with open(categories_path) as catsFile:
			for line in catsFile:
				cat, pageTitle = line[:-1].split(',', maxsplit=1)
				if cat in includeCats:
					if pageTitle.startswith(CAT_PREFIX):
						nextIncludeCats.add(pageTitle.removeprefix(CAT_PREFIX))
						if verbose:
							print(f'including "{pageTitle}"')
					else:
						includePages.add(pageTitle)
				if cat in excludeCats:
					if pageTitle.startswith(CAT_PREFIX):
						nextExcludeCats.add(pageTitle.removeprefix(CAT_PREFIX))
						if verbose:
							print(f'excluding "{pageTitle}"')
					else:
						excludePages.add(pageTitle)
		includeCats = nextIncludeCats
		excludeCats = nextExcludeCats
		nextIncludeCats = set()
		nextExcludeCats = set()

	return includePages - excludePages

if __name__ == '__main__':
	main()
