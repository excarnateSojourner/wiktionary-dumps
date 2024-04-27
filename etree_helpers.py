import re
import xml.etree.ElementTree as xet

XML_NS_PATTERN = r'^\{.+?\}'

def tag_without_xml_ns_is(elem: xet.Element, target_tag: str) -> bool:
	return elem.tag.endswith(target_tag) and bool(re.fullmatch(XML_NS_PATTERN + re.escape(target_tag), elem.tag))

def rm_xml_nses(elem: xet.Element) -> xet.Element:
	elem.tag = re.sub(XML_NS_PATTERN, '', elem.tag)
	for child in elem:
		rm_xml_nses(child)
	return elem
