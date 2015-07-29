from pint import UnitRegistry

# pint unitregistry variable used for unit conversion
unit_registry = UnitRegistry()
unit_registry.define('thms = 1 * therm = therms')
unit_registry.define('kilowatthour = kWh = kwh')
unit_registry.define('centumcubicfoot = 1 * therm = ccf = therms')
unit_registry.define('kilowattdaily = 0 * therm = kwd = kWD')
unit_registry.define('MMBTU = 10**6 * btu')
unit_registry.define('mmbtu = MMBTU')

def convert_to_therms(quantity, unit_name, ccf_conversion_factor=None):
    unit = unit_registry.parse_expression(unit_name)
    if unit == unit_registry.ccf and ccf_conversion_factor is not None:
        return ccf_conversion_factor * quantity * unit.to(
            unit_registry.therm).magnitude
    return quantity * unit.to(unit_registry.therm).magnitude

