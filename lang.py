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
	count = 0
	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		out_file.write('<mediawiki>\n  ')
		for event, node in doc:
			if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'page':
				page_node = node
				doc.expandNode(page_node)
				text_node = page_node.getElementsByTagName('text')[0]
				text_node.normalize()
				text = ''.join((node.data for node in text_node.childNodes))
				# perform a fast substring search first to avoid parsing most irrelevant pages
				if args.language in text:
					parsed = wikitextparser.parse(text)
					try:
						target_section = next(section for section in parsed.get_sections(level=2) if section.title == args.language)
						target_text = f'{parsed.get_sections(level=0)[0]}=={args.language}==\n{target_section.contents}'
						target_node = xml.dom.minidom.Text()
						target_node.replaceWholeText(target_text)
						# a little hacky, and might not be officially supported, but works for now
						text_node.childNodes = [target_node]
						out_file.write('  ')
						page_node.writexml(out_file)
						out_file.write('\n')
					# no section for target language
					except StopIteration:
						pass
				if args.verbose and count % VERBOSE_FACTOR == 0:
					print(f'{count:,}')
				count += 1
		print('</mediawiki>', file=out_file)

if __name__ == '__main__':
	main()
