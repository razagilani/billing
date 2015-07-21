"""
This file contains classes and functions used in layout analysis of PDFs
"""
from pdfminer.layout import LTTextLine, LTText, LTPage, LTTextBox, LTCurve, \
    LTImage, LTChar, LTComponent
import re

from core import init_model
from core.model import LayoutElement
from util.pdf import get_all_pdfminer_objs


def layout_elements_from_pdfminer(pages, utilbill_id):
    """
    Takes PDFMiner data and converts it to a list of LayoutElement's, as well as
     adding them to the database.
    :param pages: PDFMiner output
    :return: A list of LayoutElement's
    """
    from core.model import Session
    if Session.bind is None:
        del Session
        init_model()
        from core.model import Session
    s = Session()

    layout_elements = []
    for i in range(0, len(pages)):
        # Right now only keep track of some object types.
        # Scanned bills can have 100,000+ image/shape objects, one for each
        # character, slowing down analysis.
        page_objs = get_all_pdfminer_objs(pages[i], objtype=LTComponent,
            predicate=lambda o: isinstance(o, (LTPage, LTTextLine, LTTextBox)))
        for obj in page_objs:
            #get object type
            if isinstance(obj, LTPage):
                objtype = LayoutElement.PAGE
            elif isinstance(obj, LTTextLine):
                objtype = LayoutElement.TEXTLINE
            elif isinstance(obj, LTTextBox):
                objtype = LayoutElement.TEXTBOX
            elif isinstance(obj, LTCurve):
                objtype = LayoutElement.SHAPE
            elif isinstance(obj, LTImage):
                objtype = LayoutElement.IMAGE
            else:
                objtype = LayoutElement.OTHER

            #get text, if any
            if isinstance(obj, LTText):
                text = obj.get_text()
            else:
                text = None

            layout_elt = LayoutElement(type=objtype, x0=obj.x0, y0=obj.y0,
                x1=obj.x1, y1=obj.y1, width=obj.width, height=obj.height,
                text=text, page_num=i+1, utilbill_id=utilbill_id)
            s.add(layout_elt)
            layout_elements.append(layout_elt)

    return layout_elements

def group_layout_elements_by_page(layout_elements):
    #group layout elements by page number
    pages_layout = {}
    for layout_obj in layout_elements:
        page_num = layout_obj.page_num
        if not page_num in pages_layout:
            pages_layout[page_num] = [layout_obj]
        else:
            pages_layout[page_num] += [layout_obj]
    pages = [pages_layout[pnum] for pnum in sorted(pages_layout.keys())]

    return pages

# represents a two-dimensional, axis-aligned bounding box.
class BoundingBox:
    def __init__(self, minx, miny, maxx, maxy):
        if minx > maxx or miny > maxy:
            raise ValueError("minx and miny must be less than or equal to "
                             "maxx and maxy, respectively.")
        self.minx = minx
        self.miny = miny
        self.maxx = maxx
        self.maxy = maxy

class Corners:
    """
    Constants for the different corners of a rectangular layout object.
    """
    TOP_LEFT = 0
    TOP_RIGHT = 1
    BOTTOM_LEFT= 2
    BOTTOM_RIGHT = 3

def get_corner(obj, c):
    """
    Get a specific corner of a layout element as an (x, y) tuple.
    :param: c an integer specifying the corner, as in :Corners
    """
    x = obj.x1 if (c & 1) else obj.x0
    y = obj.y1 if (c & 2) else obj.y0
    return (x, y)


def get_text_from_bounding_box(layout_objs, boundingbox, corner):
    """
    Gets all the text on a PDF page that is within the given bounding box.
    Text from different text lines is separated by a newline.
    :param layout_objs the objects within which to search.
    """
    textlines = get_objects_from_bounding_box(layout_objs,
        boundingbox, corner, objtype=LayoutElement.TEXTLINE)
    text = '\n'.join([tl.text for tl in textlines])
    return text


def get_objects_from_bounding_box(layout_objs, boundingbox, corner, objtype=None):
    """
    Returns alls objects of the given type within a boundingbox.
    If objtype is None, all objects are returned.
    """
    search = lambda lo: (objtype is None or lo.type == objtype) and \
                        in_bounds(lo, boundingbox, corner)
    return filter(search, layout_objs)


def get_text_line(layout_objs, regexstr):
    """
    Returns the first text line found whose text matches the regex.
    :param page: The page to search
    :param regex: The regular expression string to match
    :return: An LTTextLine object, or None
    """
    regex = re.compile(regexstr, re.IGNORECASE)
    search = lambda lo: lo.type == LayoutElement.TEXTLINE and regex.search(
        lo.text)
    objs = filter(search, layout_objs)
    #sort objects by position on page
    # objs = sorted(objs, key=lambda o: (-o.y0, o.x0))
    if not objs:
        return None
    return objs[0]

def in_bounds(obj, bounds, corner):
    """
    Determines if the top left corner of a layout object is in the bounding box
    """
    testpoint = get_corner(obj, corner)
    if bounds.minx <= testpoint[0] <= bounds.maxx:
        if bounds.miny <= testpoint[1] <= bounds.maxy:
            return True

    return False


def tabulate_objects(objs):
    """
    Sort objects first into rows, by descending y values, and then
    into columns, by increasing x value
    :param objs:
    :return: A list of rows, where each row is a list of objects. The rows
    are sorted by descending y value, and the objects are sorted by
    increasing x value.
    """
    sorted_objs = sorted(objs, key=lambda o: (-o.y0, o.x0))
    table_data = []
    current_y = None
    for obj in sorted_objs:
        if obj.y0 != current_y:
            current_y = obj.y0
            current_row = []
            table_data.append(current_row)
        current_row.append(obj)

    return table_data
