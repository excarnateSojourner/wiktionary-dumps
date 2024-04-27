'''
Filter terms in a specific language out of an XML file.
'''

import argparse
import wikitextparser
import xml.etree.ElementTree as xet

import etree_helpers

VERBOSE_FACTOR = 10 ** 3

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path', help='The XML pages file to parse.')
	parser.add_argument('output_path', help='The XML pages file to write to.')
	parser.add_argument('-l', '--language', default='English', help='The full name (*not* ISO code) of the language to select. Defaults to English.')
	parser.add_argument('-v', '--verbose', action='store_true', help='Prints occasional progress updates.')
	args = parser.parse_args()

	with open(args.output_path, 'w', encoding='utf-8') as out_file:
		out_file.write('<mediawiki>\n  ')
		# only used for verbose printing
		count = 0
		for _, elem in xet.iterparse(args.input_path):
			if etree_helpers.tag_without_xml_ns_is(elem, 'page'):
				text_elem = etree_helpers.find_child(etree_helpers.find_child(elem, 'revision'), 'text')
				# perform a fast substring search first to avoid parsing most irrelevant pages
				if args.language in text_elem.text:
					parsed = wikitextparser.parse(text_elem.text)
					try:
						target_section = next(section for section in parsed.get_sections(level=2) if section.title == args.language)
						text_elem.text = f'{parsed.get_sections(level=0)[0]}=={args.language}==\n{target_section.contents}'
						elem_xml = xet.tostring(elem, encoding='unicode')
						out_file.write('  ')
						out_file.write(elem_xml)
						out_file.write('\n')
					# no section for target language
					except StopIteration:
						pass
				elem.clear()

				if args.verbose and count % VERBOSE_FACTOR == 0:
					print(f'{count:,}')
				count += 1

		out_file.write('</mediawiki>\n')

if __name__ == '__main__':
	main()
