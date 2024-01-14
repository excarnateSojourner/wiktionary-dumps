'''
Filter only English terms out of an XML file.
'''

import argparse
import re
import wikitextparser
import xml.dom.minidom
import xml.dom.pulldom

VERBOSE_FACTOR = 10 ** 4

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path', help='The XML pages file to parse.')
	parser.add_argument('output_path', help='The XML pages file to write to.')
	parser.add_argument('-l', '--language', default='English', help='The full name (*not* ISO code) of the language to select. Defaults to English.')
	parser.add_argument('-v', '--verbose', action='store_true', help='Prints occasional progress updates.')
	args = parser.parse_args()

	doc = xml.dom.pulldom.parse(args.input_path)
	# only used for verbose printing
	i = 0
	with open(args.output_path, 'w', encoding='utf-8') as outFile:
		outFile.write('<mediawiki>\n  ')
		for event, node in doc:
			if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'page':
				pageNode = node
				doc.expandNode(pageNode)
				textNode = pageNode.getElementsByTagName('text')[0]
				textNode.normalize()
				text = ''.join((node.data for node in textNode.childNodes))
				# perform a fast substring search first to avoid parsing most irrelevant pages
				if args.language in text:
					parsed = wikitextparser.parse(text)
					try:
						targetSection = next(section for section in parsed.get_sections(level=2) if section.title == args.language)
						targetText = f'{parsed.get_sections(level=0)[0]}=={args.language}==\n{targetSection.contents}'
						targetNode = xml.dom.minidom.Text()
						targetNode.replaceWholeText(targetText)
						# a little hacky, and might not be officially supported, but works for now
						textNode.childNodes = [targetNode]
						outFile.write('  ')
						pageNode.writexml(outFile)
						outFile.write('\n')
					# no section for target language
					except StopIteration:
						pass
				if args.verbose and i % VERBOSE_FACTOR == 0:
					print(i)
				i += 1
		print('</mediawiki>', file=outFile)

if __name__ == '__main__':
	main()
