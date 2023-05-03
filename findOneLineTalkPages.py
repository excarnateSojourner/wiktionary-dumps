import argparse
import re
import xml.dom.pulldom

import pulldomHelpers

VERBOSE_FACTOR = 10 ** 4
TALK_NAMESPACE = 1
TALK_PREFIX = 'Talk:'

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('talk_pages_path', help='The path of the pages file containing talk pages to check.')
	parser.add_argument('mainspace_pages_path', help='The path of the pages file containing titles of mainspace pages which contain definitions of English terms.')
	parser.add_argument('output_path', help='The path of the text file to write the results to. The results are formatted as a MediaWiki markup unordered list of links to talk pages (for English entries last modified on or after the specified date) that only contain one line.')
	parser.add_argument('start_date', help='The earliest date a talk page may have last been modified and still be included in the results. A simple string comparison is used to compare this to the last-modified dates which ISO 8601 timestamps. This means "2012", "2012-07", "2012-07-09", or even "2012-07-09T19:00" can be used to refer to the beginning of the time periods they describe.')
	parser.add_argument('-v', '--verbose', action='store_true')
	args = parser.parse_args()

	if args.verbose:
		print('Reading mainspace English titles...')
	englishTitles = set()
	mainspace_doc = xml.dom.pulldom.parse(args.mainspace_pages_path)
	for event, node in mainspace_doc:
		if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'title':
			mainspace_doc.expandNode(node)
			node.normalize()
			englishTitles.add(node.firstChild.data)

	if args.verbose:
		print('Reading talk pages...')
	count = 0
	talk_doc = xml.dom.pulldom.parse(args.talk_pages_path)
	with open(args.output_path, 'w', encoding='utf-8') as outFile:
		for event, node in talk_doc:
			if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'page':
				talk_doc.expandNode(node)
				title = pulldomHelpers.getDescendantContent(node, 'title')
				timestamp = pulldomHelpers.getDescendantContent(node, 'timestamp')
				if title.removeprefix(TALK_PREFIX) in englishTitles and timestamp >= args.start_date:
					text = pulldomHelpers.getDescendantContent(node, 'text')
					if len(text.split('\n', maxsplit=1)) == 1:
						mat = re.search('\W(2\d{3})\W.{,10}?$', text)
						if mat and mat[1] >= args.start_date[:4]:
							print(f'* [[{title}]]', file=outFile)
				if args.verbose and count % VERBOSE_FACTOR == 0:
					print(count)
				count += 1

if __name__ == '__main__':
	main()
