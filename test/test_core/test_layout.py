from unittest import TestCase

from mock import Mock

from pdfminer.layout import LTPage, LTImage, LTTextBox, LTTextLine, LTCurve, \
    LTFigure, LTLine, LTLayoutContainer
from pdfminer.pdftypes import PDFStream
from core import init_model
from core.extraction.layout import BoundingBox, get_corner, \
    get_objects_from_bounding_box, Corners, in_bounds, \
    get_text_from_bounding_box, get_text_line, tabulate_objects, \
    group_layout_elements_by_page

# init_test_config has to be called first in every test module, because
# otherwise any module that imports billentry (directly or indirectly) causes
# app.py to be initialized with the regular config  instead of the test
# config. Simply calling init_test_config in a module that uses billentry
# does not work because test are run in a indeterminate order and an indirect
# dependency might cause the wrong config to be loaded.
from core.model import LayoutElement
from test import init_test_config, create_tables, clear_db

def setUpModule():
    init_test_config()

class BoundingBoxTest(TestCase):
    def test_boundingbox_init(self):
        bbox = BoundingBox(10, 20, 110, 120)
        self.assertEqual(bbox.minx, 10)
        self.assertEqual(bbox.miny, 20)
        self.assertEqual(bbox.maxx, 110)
        self.assertEqual(bbox.maxy, 120)

        # BoundingBox throws an error if the minimum coordinates are less
        # than the maximum coordinates
        with self.assertRaises(ValueError):
            bbox = BoundingBox(110, 20, 10, 120)
        with self.assertRaises(ValueError):
            bbox = BoundingBox(10, 120, 110, 20)

class CornersTest(TestCase):
    def test_get_corner(self):
        layout_obj = Mock()
        layout_obj.x0 = 12
        layout_obj.y0 = 34
        layout_obj.x1 = 112
        layout_obj.y1 = 134
        self.assertEqual(get_corner(layout_obj, 0), (12, 34))
        self.assertEqual(get_corner(layout_obj, 1), (112, 34))
        self.assertEqual(get_corner(layout_obj, 2), (12, 134))
        self.assertEqual(get_corner(layout_obj, 3), (112, 134))

class LayoutTest(TestCase):
    def setUp(self):
        self.bbox = BoundingBox(10, 10, 110, 120)
        self.out_of_bounds_obj = LayoutElement(x0=-10, y0=-10, x1=0, y1=0,
            text="I'm out of bounds!", type=LayoutElement.TEXTLINE)
        self.in_bounds_obj = LayoutElement(x0=11, y0=11, x1=100, y1=100,
            text="I'm in bounds!", type=LayoutElement.TEXTLINE)
        self.overlap_obj = LayoutElement(x0=-10, y0=-10, x1=100, y1=100,
            text="I overlap the bounding box!", type=LayoutElement.TEXTLINE)
        self.image_obj = LayoutElement(x0=11, y0=11, x1=100, y1=100,
            type=LayoutElement.IMAGE)
        self.layout_objects = [self.out_of_bounds_obj, self.in_bounds_obj,
            self.overlap_obj, self.image_obj]

    def test_in_bounds(self):
        self.assertTrue(in_bounds(self.in_bounds_obj, self.bbox,
            Corners.TOP_LEFT))
        self.assertFalse(in_bounds(self.overlap_obj, self.bbox,
            Corners.TOP_LEFT))
        self.assertTrue(in_bounds(self.overlap_obj, self.bbox,
            Corners.BOTTOM_RIGHT))
        self.assertFalse(in_bounds(self.out_of_bounds_obj, self.bbox,
            Corners.TOP_LEFT))

    def test_layout(self):
        objects_in_bounds = get_objects_from_bounding_box(self.layout_objects,
            self.bbox,
            Corners.TOP_LEFT, LayoutElement.TEXTLINE)
        self.assertIn(self.in_bounds_obj, objects_in_bounds)
        self.assertNotIn(self.overlap_obj, objects_in_bounds)
        self.assertNotIn(self.out_of_bounds_obj, objects_in_bounds)
        self.assertNotIn(self.image_obj, objects_in_bounds)

        text_in_bounds = get_text_from_bounding_box(self.layout_objects,
            self.bbox, Corners.TOP_LEFT)
        self.assertEqual(text_in_bounds, "I'm in bounds!")

        first_text_line = get_text_line(self.layout_objects, r"I'm [a-z ]+ "
                                                             r"bounds!")
        self.assertEqual(first_text_line, self.out_of_bounds_obj)

        failed_search = get_text_line(self.layout_objects,
            r"There is no text box that matches")
        self.assertIsNone(failed_search)

class TableTest(TestCase):
    def setUp(self):
        # set up a list of layout objects organized in a table
        self.layout_objects = []
        self.tabulated_data = []
        for y in range(100, 10, -10):
            row = []
            for x in range(20, 50, 10):
                elt = LayoutElement(x0=x, y0=y, x1=x,
                    y1=y, text="%d %d text" % (x, y),
                    type=LayoutElement.TEXTLINE)
                self.layout_objects.append(elt)
                row.append(elt)
            self.tabulated_data.append(row)

        #shuffle the list, to check if we can re-sort the objects.
        from random import shuffle
        shuffle(self.layout_objects)

    def test_tabulate_data(self):
        self.assertEqual(self.tabulated_data, tabulate_objects(
            self.layout_objects))

class PDFMinerToLayoutElementTest(TestCase):
    @classmethod
    def setUpClass(cls):
        init_test_config()
        create_tables()
        init_model()
        # FakeS3Manager.start()

    @classmethod
    def tearDownClass(cls):
        # FakeS3Manager.stop()
        pass

    def tearDown(self):
        clear_db()

    def setUp(self):
        clear_db()

        # set up PDFMiner output
        # Can't use Mock since layout_elements_from_pdfminer uses isinstance
        self.page1 = LTPage(1, bbox=(0, 0, 1000, 1000))

        self.img1 = LTImage("img", Mock(autospec=PDFStream), bbox=(100, 200,
        500, 600))

        self.textbox1 = LTTextBox()
        self.textbox1.x0 = 200
        self.textbox1.y0 = 300
        self.textbox1.x1 = 600
        self.textbox1.y1 = 700
        self.textbox1.get_text = Mock(return_value="textbox1")

        self.textline1 = LTTextLine(0)
        self.textline1.x0 = 200
        self.textline1.y0 = 300
        self.textline1.x1 = 500
        self.textline1.y1 = 600
        self.textline1.get_text = Mock(return_value="textline1")

        self.page1._objs = [self.img1, self.textbox1, self.textline1]

        self.page2 = LTPage(2, bbox=(0, 0, 1000, 1000))
        self.line2 = LTLine(1, (200, 300), (500, 600))
        self.ltcont2 = LTLayoutContainer(bbox=(300, 400, 700, 800))
        self.page2._objs = [self.line2, self.ltcont2]
        self.pdfminer_pages = [self.page1, self.page2]

    def test_group_elements_by_page(self):
        le1 = LayoutElement(page_num=1)
        le2 = LayoutElement(page_num=3)
        le3 = LayoutElement(page_num=1)
        le4 = LayoutElement(page_num=2)
        le_list = [le1, le2, le3, le4]
        le_pages = group_layout_elements_by_page(le_list)
        le_pages_expected = [[le1, le3], [le4], [le2]]
        self.assertEqual(le_pages, le_pages_expected)


class LayoutElementTest(TestCase):
    def setUp(self):
        # set up PDFMiner output
        # Can't use Mock since layout_elements_from_pdfminer uses isinstance
        self.page1 = LTPage(1, bbox=(0, 0, 1000, 1000))

        self.img1 = LTImage("img", Mock(autospec=PDFStream), bbox=(100, 200,
                                                                   500, 600))

        self.textbox1 = LTTextBox()
        self.textbox1.x0 = 200
        self.textbox1.y0 = 300
        self.textbox1.x1 = 600
        self.textbox1.y1 = 700
        self.textbox1.get_text = Mock(return_value="textbox1")

        self.textline1 = LTTextLine(0)
        self.textline1.x0 = 200
        self.textline1.y0 = 300
        self.textline1.x1 = 500
        self.textline1.y1 = 600
        self.textline1.get_text = Mock(return_value="textline1")

        self.page1._objs = [self.img1, self.textbox1, self.textline1]

        self.page2 = LTPage(2, bbox=(0, 0, 1000, 1000))
        self.line2 = LTLine(1, (200, 300), (500, 600))
        self.ltcont2 = LTLayoutContainer(bbox=(300, 400, 700, 800))
        self.page2._objs = [self.line2, self.ltcont2]
        self.pdfminer_pages = [self.page1, self.page2]

    def test_pdfminer_to_layoutelement(self):
        le_pg1 = LayoutElement(type=LayoutElement.PAGE, x0=0, y0=0, x1=1000,
                               y1=1000, width=1000, height=1000, text=None,
                               page_num=1, utilbill_id=123)
        le_pg2 = LayoutElement(type=LayoutElement.PAGE, x0=0, y0=0, x1=1000,
                               y1=1000, width=1000, height=1000, text=None,
                               page_num=2, utilbill_id=123)
        le_textbox1 = LayoutElement(type=LayoutElement.TEXTBOX, x0=200, y0=300,
                                    x1=600, y1=700, page_num=1, text='textbox1',
                                    utilbill_id=123)
        le_textline1 = LayoutElement(type=LayoutElement.TEXTLINE, x0=200,
                                     y0=300, x1=500, y1=600, page_num=1,
                                     text='textline1', utilbill_id=123)

        expected_elts = [le_pg1, le_textbox1, le_textline1, le_pg2]
        layout_elts = LayoutElement.create_from_ltpages(
            self.pdfminer_pages)

        for le, exp_le in zip(layout_elts, expected_elts):
            self.assertEqual(le.type, exp_le.type)
            self.assertEqual(le.page_num, exp_le.page_num)
            self.assertEqual(le.text, exp_le.text)

            self.assertEqual(le.x0, exp_le.x0)
            self.assertEqual(le.y0, exp_le.y0)
            self.assertEqual(le.x1, exp_le.x1)
            self.assertEqual(le.y1, exp_le.y1)
