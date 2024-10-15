import argparse
import collections
import re
import xml.etree.ElementTree as xet

import etree_helpers

VERBOSITY_FACTOR = 10 ** 6

Stub = collections.namedtuple('Stub', ['id', 'ns', 'title'])

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path', help='Path of the XML or SQL file containing id / title associations. The best files for this in the dumps are stub-meta-current.xml and page.sql.')
	parser.add_argument('output_path', help='Path of the CSV file write the parsed id / title associations to. (It will be created if it does not exist.)')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.input_path.endswith('.xml'):
		stubs = parse_from_xml(args.input_path)
	elif args.input_path.endswith('.sql'):
		stubs = parse_from_sql(args.input_path)
	else:
		raise ValueError('The input path must end with either ".xml" or ".sql" to indicate how it should be parsed.')

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		for count, stub in enumerate(stubs):
			print(f'{stub.id}|{stub.ns}|{stub.title}', file=out_file)
			if args.verbose and count % VERBOSITY_FACTOR == 0:
				print(f'{count:,}')

def parse_from_xml(xml_path: str) -> collections.abc.Iterator[Stub]:
	for page in etree_helpers.pages_gen(xml_path):
		parts = []
		for child_tag in ['id', 'ns', 'title']:
			child = etree_helpers.find_child(page, child_tag)
			if child:
				parts.append(child)
			else:
				print('Warning: Skipping a page that is missing <{child_tag}>.')
				break
		if len(parts) == 3:
			yield Stub(*parts)
		page.clear()

def parse_from_sql(sql_path: str) -> collections.abc.Iterator[Stub]:
	'''Parse page.sql from the database dumps.'''
	with open(sql_path, encoding='utf-8') as sql_file:
		for sql_count, line in enumerate(sql_file):
			if line.startswith('INSERT INTO '):
				line_match = re.match(r'INSERT INTO `\w*` VALUES \((.*)\);$', line)
				if line_match:
					line_trimmed = line_match[1]
				else:
					continue
				rows = [row.split(',', maxsplit=3)[:3] for row in line_trimmed.split('),(')]
				for row in rows:
					try:
						yield Stub(int(row[0]), int(row[1]), row[2].replace("\\'", "'").replace('\\"', '"').removeprefix("'").removesuffix("'").replace('_', ' '))
					# Imperfect SQL parsing can cause int conversion to fail
					except ValueError:
						pass

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
