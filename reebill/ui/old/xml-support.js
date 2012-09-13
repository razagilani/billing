// return xpath for a given node
function getElementXPath(node)
{
	if (node == null) return null;

	var path = "";

	if (node.nodeType == 2) // an atribute node was passed in
	{
		path = "/@" + node.nodeName;
		node = node.ownerElement;
	}

	for (; node && node.nodeType == 1; node = node.parentNode)
	{
		idx = getElementIdx(node);
		xname = node.tagName;
		// all nodes must be indexed otherwise path node matches all
		// ToDo:  terminal node does not need an index?
		if (idx > 0) xname += "[" + idx + "]";
		path = "/" + xname + path;
	}

	return path;
}

function getElementIdx(elt)
{
	var count = 1;
	for (var sib = elt.previousSibling; sib ; sib = sib.previousSibling)
	{
		if(sib.nodeType == 1 && sib.tagName == elt.tagName)	count++
	}

	return count;
}


function evaluateXPath(aNode, aExpr)
{
	var xpe = new XPathEvaluator();
	var nsResolver = xpe.createNSResolver(aNode.ownerDocument == null ? aNode.documentElement : aNode.ownerDocument.documentElement);
	var result = xpe.evaluate(aExpr, aNode, nsResolver, 0, null);
	var found = new Array();
	var res;

	switch(result.resultType)
	{
	case XPathResult.NUMBER_TYPE:
		return result.numberValue;
		break;
	// ToDo add other result types as we need to
	default:
		try
		{
            // result is an XPathResult which only supports iterateNext(), 
            // so we make it look like an array for convenience
			while (res = result.iterateNext())
				found.push(res);
		} catch (e) {
			alert(e);
		}
	    return found;
	}

}
