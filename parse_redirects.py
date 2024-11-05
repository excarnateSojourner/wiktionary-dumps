import argparse
import collections
import collections.abc
import re

import parse_stubs
import etree_helpers

STUBS_VERBOSE_FACTOR = 10 ** 6

RedirectData = collections.namedtuple('RedirectData', ['src_id', 'src_title', 'dst_id', 'dst_title'])

def main():
	parser = argparse.ArgumentParser(description='Converts a redirect.sql to a more readable, flexible form.')
	parser.add_argument('sql_path', help='Path of the file giving all redirects. This file (after it is unzipped) is called "redirect.sql" in the database dumps.')
	parser.add_argument('stubs_path', help='Path of the CSV file containing page ids, namespaces, and titles, genrated by parse_stubs.py. Must contain all pages (in all namespaces) that may be the source or destination of a redirect.')
	parser.add_argument('pages_path', help='Path of the XML file containing the ids and titles of Wiktionary namespaces. This is used to add the namespace prefixes to the titles of redirect destinations (as the SQL does not have them). Any of the following files in the dumps will work equally well for this: stub-meta-current.xml, pages-articles.xml, pages-meta-current.xml.')
	parser.add_argument('output_path', help='Path of the CSV file to write the parsed redirects to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Loading namespace prefixes...')
	ns_titles = etree_helpers.get_mw_namespaces(args.pages_path)

	if args.verbose:
		print('Reading stubs...')
	# ids and titles map the exact same data in opposite directions
	stub_master = parse_stubs.StubMaster(args.stubs_path)

	if args.verbose:
		print('Reading redirect data (SQL) and writing output...')
	with open(args.sql_path, encoding='utf-8', errors='ignore') as sql_file:
		with open(args.output_path, 'w', encoding='utf-8') as out_file:
			for line in sql_file:
				if line.startswith('INSERT INTO '):
					try:
						line_trimmed = re.fullmatch(r'INSERT INTO `\w*` VALUES \((.*)\);', line[:-1])[1]
					# no match
					except TypeError:
						continue
					rows = [row.split(',', maxsplit=4)[:4] for row in line_trimmed.split('),(')]
					for row in rows:
						# if an internal redirect
						if len(row[3]) == 2:
							try:
								dst_ns_id = int(row[1])
								dst_ns_prefix = (ns_titles[dst_ns_id] + ':' if dst_ns_id in ns_titles else '')
							except KeyError:
								# destination namespace does not exist
								# encountered in 24-04-01 dump, possibly due to deletion of the concordance namespace
								continue
							dst_title = row[2].replace('_', ' ').replace("\\'", "'").replace('\\"', '"').removeprefix("'").removesuffix("'")
							try:
								print(f'{row[0]}|{stub_master.title(int(row[0]))}|{stub_master.id(dst_title)}|{dst_ns_prefix}{dst_title}', file=out_file)
							except KeyError:
								# broken redirect
								pass

def redirects_gen(path: str) -> collections.abc.Iterator[RedirectData]:
	with open(path, encoding='utf-8') as in_file:
		for line in in_file:
			fields = (line[:-1].split('|'))
			yield RedirectData(src_id=int(fields[0]), src_title=fields[1], dst_id=int(fields[2]), dst_title=fields[3])

if __name__ == '__main__':
	main()
