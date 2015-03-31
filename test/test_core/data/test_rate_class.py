from unittest import TestCase

from core.model import RateClass


class RateClassTest(TestCase):
    """Unit tests for RateClass.
    """
    def setUp(self):
        self.rate_class = RateClass('Test Rate Class')

    def test_register_templates(self):
        self.assertEqual([], self.rate_class.register_templates)
        self.assertEqual([], self.rate_class.get_register_list())
