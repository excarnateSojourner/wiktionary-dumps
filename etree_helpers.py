import collections.abc
import re
import xml.etree.ElementTree as xet

XML_NS_PATTERN = r'^\{.+?\}'

def tag_without_xml_ns_is(elem: xet.Element, target_tag: str) -> bool:
	return elem.tag.endswith(target_tag) and bool(re.fullmatch(f'({XML_NS_PATTERN})?{re.escape(target_tag)}', elem.tag))

def rm_xml_nses(elem: xet.Element) -> xet.Element:
	elem.tag = re.sub(XML_NS_PATTERN, '', elem.tag)
	for child in elem:
		rm_xml_nses(child)
	return elem

def find_child(elem: xet.Element, tag: str, xml_nses: bool = True) -> xet.Element | None:
	'''
	xml_nses indicates whether XML namespaces should be removed before comparing the tags of children of elem.
	'''
	try:
		if xml_nses:
			child = next(child for child in elem if tag_without_xml_ns_is(child, tag))
		else:
			child = next(child for child in elem if child.tag == tag)
	except StopIteration:
		return None
	return child

def pages_gen(pages_path: str) -> collections.abc.Iterator[xet.Element]:
	return (elem for _, elem in xet.iterparse(pages_path) if tag_without_xml_ns_is(elem, 'page'))

def get_mw_namespaces(path: str) -> dict[int, str]:
	mw_ns_elem = next(elem for _, elem in xet.iterparse(path) if tag_without_xml_ns_is(elem, 'namespaces'))
	rm_xml_nses(mw_ns_elem)
	return {int(child.get('key')): child.text or '' for child in mw_ns_elem if child.tag == 'namespace'}
