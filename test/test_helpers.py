import os.path

SCRIPT_DIR = os.path.dirname(__file__)

RAW_DATA_PATH = 'raw_data'
PARSED_DATA_PATH = 'parsed_data'

def raw_path(*parts: str) -> str:
	return os.path.join(SCRIPT_DIR, RAW_DATA_PATH, *parts)

def parsed_path(*parts: str) -> str:
	return os.path.join(SCRIPT_DIR, PARSED_DATA_PATH, *parts)
