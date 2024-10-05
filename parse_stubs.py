import argparse
import collections
import xml.etree.ElementTree as xet

import etree_helpers

VERBOSITY_FACTOR = 10 ** 5

Stub = collections.namedtuple('Stub', ['id', 'ns', 'title'])

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path', help='Path of the XML file containing id / title associations. The best file for this in the dumps is stub-meta-current.xml.')
	parser.add_argument('output_path', help='Path of the CSV file write the parsed id / title associations to. (It will be created if it does not exist.)')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for count, page in enumerate(etree_helpers.pages_gen(args.pages_path)):
			stub = tuple(etree_helpers.find_child(page, child).text for child in ['id', 'ns', 'title'])
			print('|'.join(stub), file=out_file)
			page.clear()

			if args.verbose and count % VERBOSITY_FACTOR == 0:
				print(f'{count:,}')

class StubMaster():
	def __init__(self, stubs_path: str):
		self.ids_to_titles = {}
		self.titles_to_ids = {}
		for stub in stubs_gen(stubs_path):
			self.ids_to_titles[stub.id] = stub.title
			self.titles_to_ids[stub.title] = stub.id

	def title(self, id_: int) -> str:
		return self.ids_to_titles[id_]

	def id(self, title: str) -> int:
		return self.titles_to_ids[title]

def stubs_gen(stubs_path: str) -> collections.abc.Iterator[Stub]:
	with open(stubs_path, encoding='utf-8') as stubs_file:
		for line in stubs_file:
			id_, ns, title = line[:-1].split('|', maxsplit=2)
			yield Stub(int(id_), int(ns), title)

if __name__ == '__main__':
	main()
