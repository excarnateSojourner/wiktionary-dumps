def getDescendantContent(node, childName):
	try:
		return getText(node.getElementsByTagName(childName)[0])
	except StopIteration:
		return None

def getText(node):
	if node.hasChildNodes():
		node.normalize()
		return node.firstChild.data
	else:
		return ''
