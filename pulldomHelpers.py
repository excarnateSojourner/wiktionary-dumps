def getDescendantContent(node, childName):
	try:
		child = node.getElementsByTagName(childName)[0]
		child.normalize()
		return child.firstChild.data
	except StopIteration:
		return None
