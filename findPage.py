import argparse
import subprocess

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('pages_path')
	parser.add_argument('title', help='The title of the page to retrieve, including any namespace prefix.')
	args = parser.parse_args()

	subprocess.run(['grep', '-Pzo', r'\s*<page>\n\s*<title>' + args.title + r'</title>\n[\w\W]*?\n\s*</page>\n', args.pages_path], check=True)

if __name__ == '__main__':
	main()
