import collections.abc
import re

VERBOSE_FACTOR = 10 ** 5

def parse_sql(path: str, verbose: bool = False) -> collections.abc.Iterator[tuple]:
	row_count = 0
	with open(path, encoding='utf-8', errors='ignore') as sql_file:
		for line in sql_file:
			if line.startswith('INSERT INTO '):
				line_match = re.fullmatch(r'INSERT INTO `\w*` VALUES (.*?);', line[:-1])
				if not line_match:
					continue
				values = line_match[1].replace('NULL', 'None')
				rows = eval(f'[{values}]')
				for row in rows:
					if verbose and row_count % VERBOSE_FACTOR == 0:
						print(f'{row_count:,}')
					row_count += 1
					yield row
