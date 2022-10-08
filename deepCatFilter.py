import argparse
import collections
import xml.dom.pulldom

CAT_PREFIX = 'Category:'

CatData = collections.namedtuple('CatData', ['catId', 'catTitle', 'pageId', 'pageTitle'])

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('categories_path', help='Path of the parsed categories file that should be used to enumerate subcategories of explicitly mentioned categories.')
	parser.add_argument('output_path', help='Path of the file to write the ids of pages in the categories to.')
	parser.add_argument('-i', '--include', required=True, nargs='+', default=[], help='Categories to include.')
	parser.add_argument('-e', '--exclude', nargs='+', default=[], help='Categories to exclude (overriding includes).')
	parser.add_argument('-n', '--input-ids', action='store_true', help='Indicates that the categories to include and exclude are specified using their ids rather than their names. Specifying ids removes the need for this program to perform time-intensive name-to-id translation.')
	parser.add_argument('-u', '--output-ids', action='store_true', help='Indicates that the output should be given as a list of IDs rather than a list of terms.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.input_ids:
		includeCats = set(int(i) for i in args.include)
		excludeCats = set(int(i) for i in args.exclude)
	else:
		if args.verbose:
			print('Translating category names to ids...')
		initialIncludes = set(c.removeprefix(CAT_PREFIX) for c in args.include)
		initialExcludes = set(c.removeprefix(CAT_PREFIX) for c in args.exclude)
		includeCats = set()
		excludeCats = set()
		for data in catsGen(args.categories_path):
			if data.catTitle in initialIncludes:
				includeCats.add(data.catId)
				initialIncludes.remove(data.catTitle)
			if data.catTitle in initialExcludes:
				excludeCats.add(data.catId)
				initialExcludes.remove(data.catTitle)
		print('If you want to include and exclude the same sets of categories later, and you want to provide their IDs instead of titles (so I do not have to translate to IDs for you), here are the IDs formatted as command-line arguments:')
		print('-i ' + ' '.join(str(i) for i in includeCats) + ' -e ' + ' '.join(str(e) for e in excludeCats) + ' -n')

	terms = catFilter(args.categories_path, includeCats, excludeCats, returnTitles=not args.output_ids, verbose=args.verbose)
	with open(args.output_path, 'w') as outFile:
		outFile.writelines(f'{term}\n' for term in terms)

def catFilter(categories_path, includeCats, excludeCats, returnTitles=False, verbose=False):
	if verbose:
		print('Looking for pages and subcategories in specified categories:')
	# collect subcats to process in the next round
	nextIncludeCats = set()
	nextExcludeCats = set()
	# collect non-cat pages in cats
	includePages = set()
	excludePages = set()

	depth = 0
	while includeCats or excludeCats:
		if verbose:
			print('', '-' * 10, f'Round {depth}', '-' * 10, sep='\n')
		for data in catsGen(categories_path):
			if data.catId in includeCats:
				if data.pageTitle.startswith(CAT_PREFIX):
					nextIncludeCats.add(data.pageId)
					if verbose:
						print(f'including "{data.pageTitle.removeprefix(CAT_PREFIX)}"')
				elif returnTitles:
					includePages.add(data.pageTitle)
				else:
					includePages.add(data.pageId)
			if data.catId in excludeCats:
				if data.pageTitle.startswith(CAT_PREFIX):
					nextExcludeCats.add(data.pageId)
					if verbose:
						print(f'excluding "{data.pageTitle.removeprefix(CAT_PREFIX)}"')
				elif returnTitles:
					excludePages.add(data.pageTitle)
				else:
					excludePages.add(data.pageId)
		includeCats = nextIncludeCats
		excludeCats = nextExcludeCats
		nextIncludeCats = set()
		nextExcludeCats = set()
		depth += 1

	return includePages - excludePages

def catsGen(categories_path):
	with open(categories_path) as catsFile:
		for line in catsFile:
			fields = (line[:-1].split(',', maxsplit=3))
			yield CatData(catId=int(fields[0]), catTitle=fields[1], pageId=int(fields[2]), pageTitle=fields[3])

if __name__ == '__main__':
	main()
