"""Test for utils.units
"""
from unittest import TestCase
from util.units import convert_to_therms

class TestUnits(TestCase):
    """Unit tests for functions in utils.units.
    """
    def test_convert_to_therms(self):
        self.assertEqual(1, convert_to_therms(1, 'therm'))
        self.assertAlmostEqual(0.0341214, convert_to_therms(1, 'kWh'))
        self.assertEqual(10, convert_to_therms(1, 'mmbtu'))

        # NOTE: no test coverage for CCF since only energy and power units
        # are supposed to be supported
