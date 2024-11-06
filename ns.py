import argparse
import xml.etree.ElementTree as xet

import etree_helpers

VERBOSE_FACTOR = 10 ** 5

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path')
	parser.add_argument('namespaces', nargs='+', help='The index(es) of the namespace(s) to select. If namespaces are separated by spaces then separate files will be created for each namespace. If they are separated by commas, the pages in all of the specified namespaces will be saved in one file. You can also use a combination: "0,1 2" will save namespaces 0 and 1 into one file, and namespace 2 into another.')
	parser.add_argument('-o', '--output-path-prefix', default='pages-')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()
	namespace_groups = []
	for comma_sep in args.namespaces:
		namespace_groups.append([int(ns) for ns in comma_sep.split(',')])

	ns_files = {}
	for group in namespace_groups:
		group_str = ','.join(str(ns) for ns in group)
		group_file = open(f'{args.output_path_prefix}{group_str}.xml', 'w', encoding='utf-8')
		for ns in group:
			ns_files[ns] = group_file
		group_file.write('<mediawiki>\n  ')

	for count, page in enumerate(etree_helpers.pages_gen(args.input_path)):
		actual_ns = int(etree_helpers.find_child(page, 'ns').text)
		out_file = ns_files.get(actual_ns)
		if out_file:
			page = etree_helpers.rm_xml_nses(page)
			xml_str = xet.tostring(page, encoding='unicode')
			out_file.write(xml_str)

		# Even though the docs say iterparse is useful for reading large documents without holding them wholly in memory, it still builds a tree in the background as it goes, using memory proportional to the size of the document!
		# Since effectively all the content in our XML is in <page>s, by clearing these as we go we prevent unnecessary hogging of memory
		page.clear()

		if args.verbose and count % VERBOSE_FACTOR == 0:
			print(f'{count:,}')

	for group in namespace_groups:
		group_file = ns_files[group[0]]
		group_file.write('</mediawiki>\n')
		group_file.close()

if __name__ == '__main__':
	main()
