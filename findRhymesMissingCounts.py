import argparse
import re
import xml.dom.pulldom

import pulldomHelpers

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path')
	parser.add_argument('output_path')
	args = parser.parse_args()

	doc = xml.dom.pulldom.parse(args.pages_path)
	with open(args.output_path, 'w', encoding='utf-8') as outFile:
		outFile.write('== List ==\n{{col4|en\n')
		for event, node in doc:
			if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'page':
				doc.expandNode(node)
				for line in pulldomHelpers.getDescendantText(node, 'text').splitlines():
					if re.match(r'\s*\* {{rhymes\|en\|', line) and not re.search(r'\|s\d*=\d+', line):
						title = pulldomHelpers.getDescendantText(node, 'title')
						outFile.write(f'| {title}\n')
						break
		outFile.write('|sort=0|collapse=0}}')

if __name__ == '__main__':
	main()
