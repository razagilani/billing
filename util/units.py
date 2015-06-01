from pint import UnitRegistry

# pint unitregistry variable used for unit conversion
ureg = UnitRegistry()
ureg.define('thms = 1 * therm = therms')
ureg.define('kilowatthour = kwh')
ureg.define('centumcubicfoot = 1 * therm = ccf = therms')
ureg.define('kilowattdaily = 0 * therm = kwd')
ureg.define('mmbtu = 10**6 * btu')

def convert_to_therms(quantity, unit_name,
                      ccf_conversion_factor=None):
    unit = ureg.parse_expression(unit_name)
    if unit == ureg.ccf and ccf_conversion_factor is not None:
        return ccf_conversion_factor * quantity * unit.to(ureg.therm).magnitude
    return quantity * unit.to(ureg.therm).magnitude

