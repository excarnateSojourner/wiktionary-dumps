import argparse
import re
import xmlParsing

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('input_path')
	parser.add_argument('output_path')
	parser.add_argument('namespace', type=int, help='The index of the namespace to filter out.')
	parser.add_argument('-v', '--verbose', action='store_true', help='Print occasional progress updates.')
	args = parser.parse_args()
	# we only use this as a str, but it should have the form of an int
	args.namespace = str(args.namespace)

	with open(args.input_path) as inFile:
		with open(args.output_path, 'w') as outFile:
			# just for verbose printing
			i = 0
			print('<mediawiki>', file=outFile)
			prePageLines, pageStartMatch = xmlParsing.readUntil(inFile, xmlParsing.PAGE_START)
			while pageStartMatch:
				nsLines, nsMatch = xmlParsing.readUntil(inFile, xmlParsing.NS_PATTERN)
				if nsMatch[1] == args.namespace:
					pageEndLines = xmlParsing.readUntil(inFile, xmlParsing.PAGE_END)[0]
					outFile.write(prePageLines[-1])
					outFile.writelines(nsLines + pageEndLines)
				prePageLines, pageStartMatch = xmlParsing.readUntil(inFile, xmlParsing.PAGE_START)
				if args.verbose and i % 10000 == 0:
					print(i)
				i += 1
			print('</mediawiki>', file=outFile)

if __name__ == '__main__':
	main()
