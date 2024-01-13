import argparse
import collections

import pulldomHelpers

VERBOSITY_FACTOR = 10 ** 5

Stub = collections.namedtuple('Stub', ['id', 'ns', 'title'])

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path', help='Path of the XML file containing id / title associations. The best file for this in the dumps is stub-meta-current.xml.')
	parser.add_argument('output_path', help='Path of the CSV file write the parsed id / title associations to. (It will be created if it does not exist.)')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for i, pageData in enumerate(pulldomHelpers.getPageDescendantText(args.pages_path, ['title', 'ns', 'id'])):
			page = Stub(pageData['id'], pageData['ns'], pageData['title'])
			out_file.write(f'{page.id}|{page.ns}|{page.title}\n')
			if args.verbose and i % VERBOSITY_FACTOR == 0:
				print(i)


def stubsGen(stubs_path):
	with open(stubs_path, encoding='utf-8') as stubs_file:
		for line in stubs_file:
			id_, ns, title = line[:-1].split('|', maxsplit=2)
			yield Stub(int(id_), int(ns), title)

if __name__ == '__main__':
	main()
