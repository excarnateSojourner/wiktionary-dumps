from typing import Iterable, Optional
import xml.dom.minidom
import xml.dom.pulldom

def get_node(doc: xml.dom.pulldom.DOMEventStream, tag: str):
	node = next(no for ev, no in doc if ev == xml.dom.pulldom.START_ELEMENT and no.tagName == tag)
	doc.expandNode(node)
	return node

def get_descendant_text(node: xml.dom.minidom.Element, childName: str) -> Optional[str]:
	try:
		return get_text(node.getElementsByTagName(childName)[0])
	except StopIteration:
		return None

def get_text(node: xml.dom.minidom.Element) -> str:
	if node.hasChildNodes():
		node.normalize()
		return node.firstChild.data
	else:
		return ''

def get_page_descendant_text(path: str, tags: list[str]) -> Iterable[dict[str, str]]:
	'''The order of the tags is very important; pages will be silently skipped if they are in the wrong order.'''
	doc = xml.dom.pulldom.parse(path)
	try:
		while True:
			values = {}
			for tag in tags:
				node = next(node for event, node in doc if event == xml.dom.pulldom.START_ELEMENT and node.tagName == tag)
				doc.expandNode(node)
				values[tag] = get_text(node)
			yield values
	except StopIteration:
		return

def get_namespace_titles(path: str) -> dict[int, str]:
	doc = xml.dom.pulldom.parse(path)
	node = next(node for event, node in doc if event == xml.dom.pulldom.START_ELEMENT and node.tagName == 'namespaces')
	doc.expandNode(node)
	return {int(ns.getAttribute('key')): get_text(ns) for ns in node.getElementsByTagName('namespace')}
