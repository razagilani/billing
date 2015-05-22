import json
from unittest import TestCase

from core.model.model import RegisterTemplate, Register


class RegisterTest(TestCase):
    """Unit tests for Register.
    """
    def setUp(self):
        pass

    def test_create_from_template(self):
        ap_dict = dict(active_periods_weekday=[0, 23],
                       active_periods_weekend=[10, 15])
        template = RegisterTemplate(register_binding='a', unit='kWh',
                                    active_periods=json.dumps(ap_dict),
                                    description='Example Register')
        register = Register.create_from_template(template)

        # fields determined by the template
        self.assertEqual('a', register.register_binding)
        self.assertEqual(ap_dict, register.get_active_periods())
        self.assertEqual('Example Register', register.description)
        self.assertEqual('kWh', register.unit)

        # fields not determined by the template, initially blank
        self.assertEqual(0, register.quantity)
        self.assertEqual(False, register.estimated)
        self.assertEqual('', register.meter_identifier)
