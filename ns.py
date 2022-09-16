import argparse
import re
import xml.dom.pulldom

import pulldomHelpers

VERBOSE_FACTOR = 10 ** 4

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path')
	parser.add_argument('output_path')
	parser.add_argument('namespace', type=int, help='The index of the namespace to filter out.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	doc = xml.dom.pulldom.parse(args.input_path)
	count = 0
	with open(args.output_path, 'w') as outFile:
		outFile.write('<mediawiki>')
		for event, node in doc:
			if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'page':
				doc.expandNode(node)
				ns = int(pulldomHelpers.getDescendantContent(node, 'ns'))
				if ns == args.namespace:
					outFile.write('\n  ')
					node.writexml(outFile)
				if args.verbose and count % VERBOSE_FACTOR == 0:
					print(count)
				count += 1

		outFile.write('\n</mediawiki>\n')

if __name__ == '__main__':
	main()
