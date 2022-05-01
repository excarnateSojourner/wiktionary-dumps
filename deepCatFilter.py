import argparse
import pulldomHelpers
import xml.dom.pulldom

CAT_PREFIX = 'Category:'

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('category_path')
	parser.add_argument('output_path')
	parser.add_argument('-i', '--include', required=True, nargs='+', default=[], help='Categories to include.')
	parser.add_argument('-e', '--exclude', nargs='+', default=[], help='Categories to exclude (overriding includes).')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	# cats being processed in this round
	includeCats = set(args.include)
	excludeCats = set(args.exclude)
	# collect subcats to process in the next round
	nextIncludeCats = set()
	nextExcludeCats = set()
	# collect non-cat pages in cats
	includePages = set()
	excludePages = set()

	while includeCats or excludeCats:
		with open(args.category_path) as catsFile:
			for line in catsFile:
				cat, pageTitle = line[:-1].split(',', maxsplit=1)
				cat = cat.removeprefix(CAT_PREFIX)
				if cat in includeCats:
					if pageTitle.startswith(CAT_PREFIX):
						nextIncludeCats.add(pageTitle.removeprefix(CAT_PREFIX))
						if args.verbose:
							print(f'including "{pageTitle}"')
					else:
						includePages.add(pageTitle)
				if cat in excludeCats:
					if pageTitle.startswith(CAT_PREFIX):
						nextExcludeCats.add(pageTitle.removeprefix(CAT_PREFIX))
						if args.verbose:
							print(f'excluding "{pageTitle}"')
					else:
						excludePages.add(pageTitle)
		includeCats = nextIncludeCats
		excludeCats = nextExcludeCats
		nextIncludeCats = set()
		nextExcludeCats = set()

	with open(args.output_path, 'w') as outFile:
		# each of the ids is already suffixed with a newline
		outFile.writelines(f'{pageTitle}\n' for pageTitle in (includePages - excludePages))

if __name__ == '__main__':
	main()
