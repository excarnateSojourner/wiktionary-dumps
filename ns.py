import argparse
import xml.etree.ElementTree as xet

import etree_helpers

VERBOSE_FACTOR = 10 ** 4

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path')
	parser.add_argument('namespaces', nargs='+', type=int, help='The index(es) of the namespace(s) to select.')
	parser.add_argument('-o', '--output-path-prefix', default='pages-')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	ns_files = {ns: open(f'{args.output_path_prefix}{ns}.xml', 'w', encoding='utf-8') for ns in args.namespaces}
	for fi in ns_files.values():
		fi.write('<mediawiki>\n  ')

	count = 0
	for page in etree_helpers.pages_gen(args.input_path):
		actual_ns = int(etree_helpers.find_child(page, 'ns').text)
		if actual_ns in args.namespaces:
			page = etree_helpers.rm_xml_nses(page)
			xml_str = xet.tostring(page, encoding='unicode')
			ns_files[actual_ns].write(xml_str)

		# Even though the docs say iterparse is useful for reading large documents without holding them wholly in memory, it still builds a tree in the background as it goes, using memory proportional to the size of the document!
		# Since effectively all the content in our XML is in <page>s, by clearing these as we go we prevent unnecessary hogging of memory
		page.clear()

		if args.verbose and count % VERBOSE_FACTOR == 0:
			print(f'{count:,}')
		count += 1

	for fi in ns_files.values():
		fi.write('</mediawiki>\n')
		fi.close()

if __name__ == '__main__':
	main()
