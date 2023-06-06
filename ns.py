import argparse
import re
import xml.dom.pulldom

import pulldomHelpers

VERBOSE_FACTOR = 10 ** 4

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path')
	parser.add_argument('output_path')
	parser.add_argument('namespaces', nargs='+', type=int, help='The index(es) of the namespace(s) to select.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()
	namespaces = set(args.namespaces)

	doc = xml.dom.pulldom.parse(args.input_path)
	count = 0
	with open(args.output_path, 'w', encoding='utf-8') as outFile:
		outFile.write('<mediawiki>')
		for event, node in doc:
			if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'page':
				pageNode = node
				nsNode = next(no for ev, no in doc if ev == xml.dom.pulldom.START_ELEMENT and no.tagName == 'ns')
				doc.expandNode(nsNode)
				ns = int(pulldomHelpers.getText(nsNode))
				if ns in namespaces:
					doc.expandNode(pageNode)
					outFile.write('\n  ')
					pageNode.writexml(outFile)
				if args.verbose and count % VERBOSE_FACTOR == 0:
					print(count)
				count += 1

		outFile.write('\n</mediawiki>\n')

if __name__ == '__main__':
	main()
