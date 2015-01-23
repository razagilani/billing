from pint import UndefinedUnitError
from core import ureg

def convert_to_therms(quantity, unit_name,
                       ccf_conversion_factor=None):
    unit = ureg.parse_expression(unit_name)
    if unit == ureg.ccf and ccf_conversion_factor is not None:
        return ccf_conversion_factor * quantity * unit.to(
            ureg.therm).magnitude
    return quantity * unit.to(ureg.therm).magnitude

