import argparse
import os
import os.path

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('dir')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	parse_dump(args.dir, args.verbose)

def parse_dump(dir_: str, verbose: bool = False) -> None:
	os.chdir(dir_)
	filenames = os.listdir()

	for filename in filenames:
		if filename.endswith('.bz2') or filename.endswith('.gz'):
			print(f'Warning: {filename} needs to be uncompressed before it can be parsed.')

	try:
		stubs = next(file for file in filenames if file.endswith('page.sql'))
		parsing.parse_stubs.parse_stubs(filename, 'stubs.csv', verbose)
	except StopIteration:
		print('Error: page.sql is missing.')
		exit()

	for filename in filenames:
		if filename.endswith('categorylinks.sql'):
			parsing.parse_cats.parse_cats(filename, 'stubs.csv', 'cats.csv', verbose)
