import argparse
import collections.abc
import re
import typing

import parsing.parse_stubs
import parsing.etree_helpers

STUBS_VERBOSE_FACTOR = 10 ** 6

RedirectData = typing.NamedTuple('RedirectData', [('src_id', int), ('src_ns', int), ('src_title', str), ('dst_id', int), ('dst_ns', int), ('dst_title', str)])

def main():
	parser = argparse.ArgumentParser(description='Converts a redirect.sql to a more readable, flexible form.')
	parser.add_argument('sql_path', help='Path of the file giving all redirects. This file (after it is unzipped) is called "redirect.sql" in the database dumps.')
	parser.add_argument('stubs_path', help='Path of the CSV file containing page ids, namespaces, and titles, genrated by parse_stubs.py. Must contain all pages (in all namespaces) that may be the source or destination of a redirect.')
	parser.add_argument('output_path', help='Path of the CSV file to write the parsed redirects to.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	parse_redirects(**vars(args))

def parse_redirects(sql_path: str, stubs_path: str, output_path: str, verbose: bool = False) -> None:
	if verbose:
		print('Reading stubs...')
	stub_master = parsing.parse_stubs.StubMaster(stubs_path)

	if verbose:
		print('Reading redirect data (SQL) and writing output...')
	with open(output_path, 'w', encoding='utf-8') as out_file:
		for row in parsing.sql_helpers.parse_sql(sql_path, verbose):
			# If an internal redirect
			if not row[3]:
				src_id = row[0]
				dst_ns = row[1]
				dst_title = row[2].replace('_', ' ')
				try:
					out_file.write(f'{src_id}|{stub_master.ns(src_id)}|{stub_master.title(src_id)}|{stub_master.id(dst_title, dst_ns)}|{dst_ns}|{dst_title}\n')
				except KeyError:
					# Broken redirect
					continue

def redirects_gen(path: str) -> collections.abc.Iterator[RedirectData]:
	with open(path, encoding='utf-8') as in_file:
		for line in in_file:
			src_id, src_ns, src_title, dst_id, dst_ns, dst_title = line[:-1].split('|', maxsplit=5)
			yield RedirectData(int(src_id), int(src_ns), src_title, int(dst_id), int(dst_ns), dst_title)

def add_redirects(pages: set[int] | set[str], redirects_path: str) -> set[int] | set[str]:
	'''
	Add all pages that redirect to any of the specified pages to the set of pages, and return this set.
	Assume there are no double redirects.
	'''

	if isinstance(next(iter(pages)), int):
		for red in redirects_gen(redirects_path):
			if red.dst_id in pages:
				pages.add(red.src_id)
	# Pages are page titles
	else:
		for red in redirects_gen(redirects_path):
			if red.dst_title in pages:
				pages.add(red.src_title)
	return pages


if __name__ == '__main__':
	main()
