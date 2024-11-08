import collections.abc
import re

def parse_sql(path: str) -> collections.abc.Iterator[tuple]:
	with open(path, encoding='utf-8', errors='ignore') as sql_file:
		for line in sql_file:
			if line.startswith('INSERT INTO '):
				line_match = re.fullmatch(r'INSERT INTO `\w*` VALUES (.*?);', line[:-1])
				if not line_match:
					continue
				values = line_match[1].replace('NULL', 'None')
				rows = eval(f'[{values}]')
				for row in rows:
					yield row
