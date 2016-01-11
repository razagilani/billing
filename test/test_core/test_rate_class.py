from unittest import TestCase

from core.model import RateClass, Register


class RateClassTest(TestCase):
    """Unit tests for RateClass.
    """
    def setUp(self):
        self.rate_class = RateClass('Test Rate Class')

    def test_register_templates(self):
        register_templates = self.rate_class.register_templates
        self.assertEqual(1, len(register_templates))
        template = register_templates[0]
        self.assertEqual(Register.TOTAL, template.register_binding)
        # no assertions about units or TOU data because there is no good way
        # to determine those right now

        registers = self.rate_class.get_register_list()
        self.assertEqual(1, len(registers))
        register = registers[0]
        self.assertEqual(Register.TOTAL, register.register_binding)
