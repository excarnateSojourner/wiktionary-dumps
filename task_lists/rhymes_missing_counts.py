import argparse
import re
import xml.dom.pulldom

import pulldom_helpers

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path')
	parser.add_argument('output_path')
	args = parser.parse_args()

	doc = xml.dom.pulldom.parse(args.pages_path)
	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		out_file.write('== List ==\n{{col4|en\n')
		for event, node in doc:
			if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'page':
				doc.expandNode(node)
				for line in pulldom_helpers.get_descendant_text(node, 'text').splitlines():
					if re.match(r'\s*\* {{rhymes\|en\|', line) and not re.search(r'\|s\d*=\d+', line):
						title = pulldom_helpers.get_descendant_text(node, 'title')
						out_file.write(f'| {title}\n')
						break
		out_file.write('|sort=0|collapse=0}}')

if __name__ == '__main__':
	main()
