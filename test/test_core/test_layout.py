from datetime import date, datetime
import os
from unittest import TestCase, skip

from boto.s3.connection import S3Connection
from celery.result import AsyncResult
from mock import Mock, NonCallableMock

# init_test_config has to be called first in every test module, because
# otherwise any module that imports billentry (directly or indirectly) causes
# app.py to be initialized with the regular config  instead of the test
# config. Simply calling init_test_config in a module that uses billentry
# does not work because test are run in a indeterminate order and an indirect
# dependency might cause the wrong config to be loaded.
from core.extraction.layout import BoundingBox, get_corner, \
    get_objects_from_bounding_box, Corners, in_bounds, get_text_from_bounding_box, \
    get_text_line, tabulate_objects
from core.model.model import LayoutElement
from test import init_test_config
init_test_config()

from core import init_model, ROOT_PATH
from core.bill_file_handler import BillFileHandler
from core.extraction.extraction import Field, Extractor, Main, TextExtractor
from core.extraction.applier import Applier
from core.model import UtilBill, UtilityAccount, Utility, Session, Address, \
    RateClass, Charge
from core.utilbill_loader import UtilBillLoader
from exc import ConversionError, ExtractionError, MatchError, ApplicationError
from test import init_test_config, clear_db, create_tables
from test.setup_teardown import FakeS3Manager

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


