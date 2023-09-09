import argparse
import xml.dom.minidom
import xml.dom.pulldom

import pulldomHelpers

VERBOSE_FACTOR = 10 ** 4

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path')
	parser.add_argument('namespaces', nargs='+', type=int, help='The index(es) of the namespace(s) to select.')
	parser.add_argument('--output-path-prefix', '-o', default='pages-')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	doc = xml.dom.pulldom.parse(args.input_path)
	count = 0
	ns_files = {ns: open(f'{args.output_path_prefix}{ns}.xml', 'w', encoding='utf-8') for ns in args.namespaces}
	for fi in ns_files.values():
		fi.write('<mediawiki>')

	for event, pageNode in doc:
		if event == xml.dom.pulldom.START_ELEMENT and pageNode.tagName == 'page':
			doc.expandNode(pageNode)
			actual_ns = int(pulldomHelpers.getDescendantText(pageNode, 'ns'))
			try:
				ns_files[actual_ns].write(f'\n  {pageNode.toxml()}')
			except KeyError:
				pass
			if args.verbose and count % VERBOSE_FACTOR == 0:
				print(count)
			count += 1

	for fi in ns_files.values():
		fi.write('\n</mediawiki>\n')
		fi.close()

if __name__ == '__main__':
	main()
