def getDescendantContent(node, childName):
	try:
		child = node.getElementsByTagName(childName)[0]
		if child.hasChildNodes():
			child.normalize()
			return child.firstChild.data
		else:
			return ''
	except StopIteration:
		return None
