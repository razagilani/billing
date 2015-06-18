import re

from pdfminer.converter import TextConverter, PDFPageAggregator
from pdfminer.layout import LAParams, LTComponent, LTChar, LTTextLine
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFSyntaxError, PDFParser

#represents a two-dimensional, axis-aligned bounding box.
from util.pdfminer_util import fix_pdfminer_cid

class BoundingBox:
    def __init__(self, minx, miny, maxx, maxy):
        self.minx = minx
        self.miny = miny
        self.maxx = maxx
        self.maxy = maxy

CORNERS = {
    'top left' : 0,
    'top right' : 1,
    'bottom left' : 2,
    'bottom right' : 3,
}

def get_corner(obj, c):
    x = obj.x1 if (c & 1) else obj.x0
    y = obj.y1 if (c & 2) else obj.y0
    return (x, y)

def get_text_from_boundingbox(ltobject, boundingbox, corner):
    """
    Gets all the text on a PDF page that is within the given bounding box.
    Text from different LTTextLines is separated by a newline.
    :param ltobject: The object, such as a page, within which to search.
    :param boundingbox:
    :return:
    """
    textlines = get_objects_from_bounding_box(ltobject,
        boundingbox, corner, objtype=LTTextLine)
    text = '\n'.join([tl.get_text() for tl in textlines])
    #for pdfminer unicode issues, fixes occurences of (cid:<char code>)
    text = fix_pdfminer_cid(text)
    return text

def get_objects_from_bounding_box(ltobject, boundingbox, corner, objtype=None):
    """
    Returns alls objects of the given type within a boundingbox.
    If objtype is None, all objects are returned.
    :param ltobject:
    :param boundingbox:
    :param corner:
    :param objtype:
    :return:
    """
    return get_all_objs(ltobject,
                        objtype=objtype,
                        predicate=lambda o: in_bounds(o, boundingbox, corner))

def get_text_line(page, regexstr):
    """
    Returns the first LTTextLine object found whose text matches the regex.
    :param page: The page to search
    :param regex: The regular expression string to match
    :return: An LTTextLine object, or None
    """
    regex = re.compile(regexstr, re.IGNORECASE)
    objs = get_all_objs(page, LTTextLine,
        lambda o: regex.search(o.get_text()))
    if not objs:
        return None
    return objs[0]

def get_all_objs(ltobject, objtype=None, predicate=None):
    """
    Obtains all the subobjects of a given object, including the object itself,
    that are of the given type and satisfy the given predicate.
    :param ltobject: The given layout object
    :param objtype: Only return objects of this type
    :param predicate: Only return objects that satisfay this predicate function.
    :return: A list of layout objects that match the above criteria.
    """
    objs = []

    def get_obj(obj):
        if not objtype or isinstance(obj, objtype):
            if not predicate or predicate(obj):
                objs.append(obj)

    apply_recursively_to_ltobj(ltobject, get_obj)
    return objs


def apply_recursively_to_ltobj(obj, func):
    """
    Applies the function 'func' recursively to the layout object 'obj' and all
    its sub-objects.
    :return: No return value.
    """
    func(obj)
    if hasattr(obj, "_objs"):
        for child in obj._objs:
            apply_recursively_to_ltobj(child, func)


def in_bounds(obj, bounds, corner):
    """
    Determines if the top left corner of a layout object is in the bounding box
    """
    testpoint = get_corner(obj, corner)
    if bounds.minx <= testpoint[0] <= bounds.maxx:
        if bounds.miny <= testpoint[1] <= bounds.maxy:
            return True

    return False