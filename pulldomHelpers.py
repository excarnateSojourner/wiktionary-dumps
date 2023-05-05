from typing import Iterable, Optional
import xml.dom.minidom
import xml.dom.pulldom

def getDescendantContent(node: xml.dom.minidom.Element, childName: str) -> Optional[str]:
	try:
		return getText(node.getElementsByTagName(childName)[0])
	except StopIteration:
		return None

def getText(node: xml.dom.minidom.Element) -> str:
	if node.hasChildNodes():
		node.normalize()
		return node.firstChild.data
	else:
		return ''

def getPageDescendantText(path: str, tags: list[str]) -> Iterable[dict[str, str]]:
	doc = xml.dom.pulldom.parse(path)
	try:
		while True:
			values = {}
			for tag in tags:
				node = next(node for event, node in doc if event == xml.dom.pulldom.START_ELEMENT and node.tagName == tag)
				doc.expandNode(node)
				values[tag] = getText(node)
			yield values
	except StopIteration:
		return
