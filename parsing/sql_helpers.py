import collections.abc
import re

VERBOSE_FACTOR = 500

def parse_sql(path: str, verbose: bool = False) -> collections.abc.Iterator[tuple]:
	with open(path, encoding='utf-8', errors='ignore') as sql_file:
		for count, line in enumerate(sql_file):
			if verbose and count % VERBOSE_FACTOR == 0:
				print(f'{count:,}')
			if line.startswith('INSERT INTO '):
				line_match = re.fullmatch(r'INSERT INTO `\w*` VALUES (.*?);', line[:-1])
				if not line_match:
					continue
				values = line_match[1].replace('NULL', 'None')
				rows = eval(f'[{values}]')
				for row in rows:
					yield row
