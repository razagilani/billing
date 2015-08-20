"""
This file contains classes and functions used in layout analysis of PDFs
"""
import re


# different types of layout objects, e.g. a page, an image, text, etc.
PAGE = "page"
TEXTBOX = "textbox"
TEXTLINE = "textline"
SHAPE = "shape"
IMAGE = "image"
OTHER = "other"
LAYOUT_TYPES = [PAGE, TEXTBOX, TEXTLINE, SHAPE, IMAGE, OTHER]

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
    x = obj.bounding_box.x1 if (c & 1) else obj.bounding_box.x0
    y = obj.bounding_box.y0 if (c & 2) else obj.bounding_box.y1
    return (x, y)


def get_text_from_bounding_box(layout_objs, boundingbox, corner):
    """
    Gets all the text on a PDF page that is within the given bounding box.
    Text from different text lines is separated by a newline.
    :param layout_objs the objects within which to search.
    """
    search = lambda lo: lo.type == TEXTLINE and \
                        in_bounds(lo, boundingbox, corner)
    textlines = filter(search, layout_objs)
    text = '\n'.join([tl.text for tl in textlines])
    return text

def get_text_line(layout_objs, regexstr):
    """
    Returns the first text line found whose text matches the regex.
    :param page: The page to search
    :param regex: The regular expression string to match
    :return: A LayoutElement object, or None
    """
    regex = re.compile(regexstr, re.IGNORECASE)
    search = lambda lo: lo.type == TEXTLINE and regex.search(
        lo.text)
    objs = filter(search, layout_objs)
    if not objs:
        return None
    return objs[0]

def in_bounds(obj, bounds, corner):
    """
    Determines if a corner of a layout object is in the bounding box
    """
    testpoint = get_corner(obj, corner)
    if bounds.x0 <= testpoint[0] <= bounds.x1:
        if bounds.y0 <= testpoint[1] <= bounds.y1:
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
    sorted_objs = sorted(objs, key=lambda o: (-o.bounding_box.y1,
    o.bounding_box.x0))
    table_data = []
    current_y = None
    for obj in sorted_objs:
        if obj.bounding_box.y1 != current_y:
            current_y = obj.bounding_box.y1
            current_row = []
            table_data.append(current_row)
        current_row.append(obj)

    return table_data
