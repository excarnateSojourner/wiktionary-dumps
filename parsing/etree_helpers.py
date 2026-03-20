import collections.abc
import re
import xml.etree.ElementTree as xet

XML_NS_PATTERN = r'^\{.+?\}'

def tag_without_xml_ns_is(elem: xet.Element, target_tag: str) -> bool:
	if elem.tag.endswith(target_tag):
		return bool(re.fullmatch(f'({XML_NS_PATTERN})?{re.escape(target_tag)}', elem.tag))
	return False

def rm_xml_nses(elem: xet.Element) -> xet.Element:
	elem.tag = re.sub(XML_NS_PATTERN, '', elem.tag)
	for child in elem:
		rm_xml_nses(child)
	return elem

def pages_gen(pages_path: str) -> collections.abc.Iterator[xet.Element]:
	for end_event, elem in xet.iterparse(pages_path):
		if tag_without_xml_ns_is(elem, 'page'):
			yield rm_xml_nses(elem)

			# Even though the docs say iterparse is useful for reading large documents without holding them wholly in memory, it still builds a tree in the background as it goes, using memory proportional to the size of the document!
			# Since effectively all the content in our XML is in <page>s, by clearing these as we go we prevent unnecessary hogging of memory
			elem.clear()
