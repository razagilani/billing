"""Code related to applying data extracted from utility bill files to UtilBill
objects so they can be stored in the database. Everything that depends
specifically on the UtilBill class should go here.
"""
import re
import regex
from sqlalchemy.orm.exc import NoResultFound

from core.model import Session, Address, Supplier
from core.model.model import ChargeNameMap
from core.model.utilbill import Charge
from exc import ConversionError, NoRSIBindingError


def convert_table_charges(rows):
    """
    Converts a list of charges extracted from a TableField.
    The inputs is a list of rows, and each row is a list of cells; each cell
    is a string value.
    """
    # TODO get charge name map by utility

    # default charge type is DISTRIBUTION
    charge_type = Charge.DISTRIBUTION
    charge_names_map = _get_charge_names_map()
    charges = []
    for i in range (0, len(rows)):
        row = rows[i]
        if not row:
            continue

        if len(row) == 1:
            # check if this table cell contains a name and a price in the
            # same box
            m = re.search("([a-z].+?)([$\-\d.,]+){2,}$", row[0])
            if m:
                row = m.groups()
            else:
                # If a label is in all caps or has a colon at the end, assume
                # it's some sort of heading indicating charge type.
                if not re.search(r"[a-z]", row[0]) or re.search(":$", row[0]):
                    # check if this row is a header for a type of charge.
                    if re.search(r"suppl[iy]|generation|transmission", row[0],
                                 re.IGNORECASE):
                        charge_type = Charge.SUPPLY
                    else:
                        charge_type = Charge.DISTRIBUTION
                else:
                    # Otherwise, assume this row is part of the next row's charge name
                    # that got wrapped.
                    # if the next row exists, and is an actual charge row,
                    # append this current row's text to the next row's name
                    # TODO In some bills the value is on the last line of the
                    # charge name, other times it's on the first
                    # a better way is needed to detect overflowing cells.
                    if i < len(rows) - 1 and len(rows[i+1]) > 1:
                        rows[i+1][0] = row[0] + " " + rows[i+1][0]
                continue
        try:
            charges.append(process_charge(charge_names_map, row, charge_type))
        except NoRSIBindingError:
            # if no rsi binding is found, skip this bill.
            continue
    return filter(None, charges)

def convert_unit(unit):
    """
    Convert units found in bills to standardized formats.
    """
    if unit in Charge.CHARGE_UNITS:
        return unit
    # by default, if no unit then assume dollars
    if not unit:
        return "dollars"
    if unit == "th":
        return "therms"
    if unit == "$":
        return "dollars"
    # if unit is not valid, raise an error
    raise ConversionError('unit "%s" is not in set of allowed units.' %
                          unit)

def process_charge(charge_names_map, row, ctype=Charge.DISTRIBUTION):
    """
    Processes a row of text values to create a single charge with the given
    charge type.
    :param row: A list of strings of length at least 2.
    :param ctype: The type of the charge
    :return: a Charge object
    """
    if len(row) < 2:
        raise ConversionError('Charge row %s must have at least two '
                              'values.')

    num_format = r"[\d,.]+"
    # for prices, negative sign can appear on both sides of dollar sign
    price_format = r"-?\$?-?[\d,.]+"
    # this is based off the units currently in the charge table in the database.
    # these will probably have to be updated
    unit_format = r"kWd|kWh|dollars|th|therms|BTU|MMBTU|\$"
    # matches text of the form <quantity> <unit> x <rate>
    #   e.g. 1,362.4 TH x .014
    # TODO only works for wash gas, pepco bills
    register_format = r"(%s)\s*(%s)\s*[@x]\s*\$?(%s)" % (num_format,
    unit_format,
    num_format)

    # first cell in row is the name of the charge (and sometimes contains
    # rate info as well), while the last cell in row is the value of the
    # charge.
    text = row[0]
    value = row[-1]
    if not text or not value:
        raise ConversionError('Table row ("%s", "%s") contains an empty '
                              'element.' % row)

    # set up default values
    rsi_binding = target_total = None
    rate = 0
    description = unit = ''

    # if row does not end with a price, this is not a charge.
    match = re.search(price_format, value)
    if match:
        target_total = float(re.sub(r'[,$]', '', match.group(0)))
    else:
        return None

    # determine unit for charge, from either the value (e.g. "$456")
    # or from the name e.g. "Peak Usage (kWh):..."
    match = re.search(r"(%s)" % unit_format, value)
    if match:
        unit = match.group(0)
    else:
        match = re.match(r"(\(%s\))" % unit_format, text)
        if match:
            unit = match.group(0)
    unit = convert_unit(unit)

    # check if charge refers to a register
    # register info can appear in first cell, or in a middle column,
    # so check all columns
    for i in range(0, len(row)):
        cell = row[i]
        match = re.search(r"(.*?)\s*%s" % register_format, cell,
            re.IGNORECASE)
        if match:
            reg_quantity = match.group(2)
            reg_unit = match.group(3)
            rate = float(match.group(4))
            # TODO create register, formula
        # register info is often in same text box as the charge name.
        # If this is the case, separate the description from the other info.
        if i == 0:
            description = match.group(1) if match else cell

    # Get rsi binding from database.
    # TODO also filter by charge type in this query?
    rsi_binding = _get_rsi_binding_from_name(charge_names_map, description)
    
    return Charge(description=description, unit=unit, rate=rate,
        rsi_binding=rsi_binding, type=ctype, target_total=target_total)

def _get_charge_names_map():
    """
    Return a list of charge name mappings.
    Each item is a ChargeNameMap row, containing a regex that matches a
    charge's description, and a corresponding rsi_binding.
    :return: A list of ChargeNameMap objects.
    """
    s = Session()
    return s.query(ChargeNameMap).all()

def _get_rsi_binding_from_name(charge_names_map, charge_name):
    """
    Get the RSI binding for a charge name
    :param charge_names_map: A list of ChargeNameMap rows
    :param charge_name: The charge's name, as seen on a bill.
    :return: An RSI binding corresponding to the charge, as a string
    """
    rsi_bindings = []
    # sanitize charge name
    charge_name_clean = Charge.description_to_rsi_binding(charge_name)

    # look for matching patterns in charge_names_map
    for charge_entry in charge_names_map:
        charge_regex = charge_entry.display_name_regex
        if regex.fullmatch("(%s){i<=3,d<=3,e<=3}" % charge_regex,
                charge_name_clean,
                regex.IGNORECASE):
            rsi_bindings.append(charge_entry.rsi_binding)
    if len(rsi_bindings) > 1:
        raise ConversionError('Multiple (%d) RSI bindings match to charge name '
                              '"%s": %s' % (len(rsi_bindings), charge_name,
                                rsi_bindings))
    elif len(rsi_bindings) == 0:
        # use sanitized name as rsi_binding
        # surround name with ^ and $ to ensure that a very short charge name
        # doesn't lead to ambiguous matches for other charges.
        charge_name_regex = re.escape(charge_name_clean)
        new_cnm = ChargeNameMap(display_name_regex=charge_name_regex,
            rsi_binding=charge_name_clean, reviewed=False)
        s = Session()
        s.add(new_cnm)
        # need to do this, since charge_names_map is only updated once per bill.
        # This will create duplicate entries if bill has multiple of the same
        #  charge name.
        charge_names_map.append(new_cnm)
        return charge_name_clean
    return rsi_bindings[0]


def convert_wg_charges_std(text):
    """Function to convert a string containing charges from a particular
    Washington Gas bill format into a list of Charges. There might eventually
    be many of these.
    """
    # TODO: it's bad to do a query in here. also, when there are many of
    # these functions, this creates duplicate code both for loading the name map
    # and for using it to convert names into rsi_bindings. it probably should
    # be an argument.
    charge_names_map = _get_charge_names_map()
    regexflags = re.IGNORECASE | re.MULTILINE | re.DOTALL
    groups = r'DISTRIBUTION SERVICE(.*?)NATURAL GAS\s?SUPPLY SERVICE(.*?)TAXES(.*?' \
             r'Total Current Washington Gas Charges)(.*?)' \
             r'Total Washington Gas Charges This Period'
    charge_name_exp = r"([a-z]['a-z \-]+?[a-z])\s*(?:[\d@\n]|$)"
    dist_charge_block, supply_charge_block, taxes_charge_block, charge_values_block = re.search(groups, text, regexflags).groups()
    dist_charge_names = re.findall(charge_name_exp, dist_charge_block, regexflags)
    supply_charge_names = re.findall(charge_name_exp, supply_charge_block, regexflags)
    taxes_charge_names = re.findall(charge_name_exp, taxes_charge_block, regexflags)
    charge_values_lines = filter(None, re.split("\n+", charge_values_block,
        regexflags))

    # read charges backwards, because WG bills include previous bill amounts at top of table
    charge_values_lines = charge_values_lines[::-1]
    charge_data = [(taxes_charge_names[::-1], Charge.DISTRIBUTION),
        (supply_charge_names[::-1], Charge.SUPPLY),
        (dist_charge_names[::-1], Charge.DISTRIBUTION)]

    def process_charge(name, value, ct):
        rsi_binding = _get_rsi_binding_from_name(charge_names_map, name)
        return Charge(rsi_binding, name=name, target_total=float(value),
            type=ct, unit='therms')
    charges = []
    for names, type in charge_data:
        for charge_name in names:
            if not charge_values_lines:
                break
            charge_value_text = charge_values_lines[0]
            del charge_values_lines[0]
            match = re.search(r"\$\s+(-?\d+(?:\.\d+)?)", charge_value_text)
            if not match:
                continue
            charge_value = float(match.group(1))
            charges.append(process_charge(charge_name, charge_value, type))
    # reverse list, remove last item ('Total Current Washington Gas Charges')
    return charges[:0:-1]

def convert_wg_charges_wgl(text):
    """Function to convert a string containing charges from a particular
    Washington Gas bill format into a list of Charges. There might eventually
    be many of these.
    """
    # TODO: it's bad to do a query in here. also, when there are many of
    # these functions, this creates duplicate code both for loading the name map
    # and for using it to convert names into rsi_bindings. it probably should
    # be an argument.
    charge_names_map = _get_charge_names_map()
    groups = 'DISTRIBUTION SERVICE(.*?)NATURAL GAS\s?SUPPLY SERVICE(.*)TAXES(.*?)' \
             'Total Current Washington Gas Charges(.*?)' \
             'Total Washington Gas Charges This Period'
    regexflags = re.IGNORECASE | re.MULTILINE | re.DOTALL
    dist_charge_block, supply_charge_block, taxes_charge_block, charge_values_block = re.search(groups, text, regexflags)
    dist_charge_names = re.split("\n+", dist_charge_block, regexflags)
    supply_charge_names = re.split("\n+", supply_charge_block, regexflags)
    taxes_charge_names = re.split("\n+", taxes_charge_block, regexflags)
    charge_values_names = re.split("\n+", charge_values_block, regexflags)

    charge_name_exp = r"([a-z]['a-z ]+?[a-z])\s*[\d@\n]"
    # read charges backwards, because WG bills include previous bill amounts at top of table
    charge_values_names = charge_values_names[::-1]
    charge_data = [(taxes_charge_names[::-1], Charge.DISTRIBUTION),
        (supply_charge_names[::-1], Charge.SUPPLY),
        (dist_charge_names[::-1], Charge.DISTRIBUTION)]

    def process_charge(name, value, ct):
        rsi_binding = _get_rsi_binding_from_name(charge_names_map, name)
        return Charge(rsi_binding, name=name, target_total=float(value), type=ct)

    charges = []
    for names, type in charge_data:
        for n in names:
            if not charge_values_names:
                break
            charge_value_text = charge_values_names[0]
            del charge_values_names[0]
            match = re.search(r"\$\s+(-?\d+(?:\.\d+)?)", charge_value_text)
            if not match:
                continue
            charge_value = float(match.group(1))

            match = re.search(charge_name_exp, n, regexflags)
            if not match:
                continue
            charge_name = match.group(1)

            charges.append(process_charge(charge_name, charge_value, type))

    return charges


def pep_old_convert_charges(text):
    """
    Given text output from a pepco utility bill PDF that contains
    supply/distribution/etc charges, parses the individual charges
    and returns a list of Charge objects.
    :param text - the text containing both distribution and supply charges.
    :returns A list of Charge objects representing the charges from the bill
    """
    # TODO deal with external suppliers
    # TODO find a better method for categorizing charge names
    charge_names_map = _get_charge_names_map()


    distribution_charges_exp = r'Distribution Services:(.*?)Generation Services:'
    supply_charges_exp = r'Generation Services:(.*?)Transmission Services:'
    transmission_charges_exp = r'Transmission Servces:(.*?Total Charges - Transmission)'
    charge_values_exp = r'Total Charges - Transmission(.*?)CURRENT CHARGES THIS PERIOD'

    regex_flags =  re.DOTALL | re.IGNORECASE | re.MULTILINE
    dist_charges_block = re.search(distribution_charges_exp, text, regex_flags).group(1)
    supply_charges_block = re.search(supply_charges_exp, text, regex_flags).group(1)
    trans_charges_block = re.search(transmission_charges_exp, text, regex_flags).group(1)
    charge_values_block = re.search(charge_values_exp, text, regex_flags).group(1)

    dist_charges_names = re.split(r"\n+", dist_charges_block, regex_flags)
    supply_charges_names = re.split(r"\n+", supply_charges_block, regex_flags)
    trans_charges_names = re.split(r"\n+", trans_charges_block, regex_flags)
    charge_values = re.split(r"\n+", charge_values_block, regex_flags)
    trans_charges_names_clean = []
    # clean rate strings (eg 'at 0.0000607 per KWH') from transmission charges.
    for name in trans_charges_names:
        if not name or re.match(r'\d|at|Includ|Next', name):
            continue
        trans_charges_names_clean.append(name)

    def process_charge(name, value, ct):
        rsi_binding = _get_rsi_binding_from_name(charge_names_map, name)
        return Charge(rsi_binding, name=name, target_total=float(value),
            type=ct, unit='therms')

    charges = []
    charge_data = [(dist_charges_names, Charge.DISTRIBUTION),
        (supply_charges_names, Charge.SUPPLY), (trans_charges_names_clean,
        Charge.DISTRIBUTION)]
    for names, type in charge_data:
        for charge_name in names:
            if not charge_name:
                continue
            # in case some charges failed to be read
            if not charge_values:
                break
            charge_num_text = charge_values[0]
            del charge_values[0]
            charge_num = float(re.search(r'\d+(?:\.\d+)?', charge_num_text))
            charges.append(process_charge(charge_name, charge_num, type))

    return charges


def pep_new_convert_charges(text):
    """
    Given text output from a pepco utility bill PDF that contains supply/distribution/etc charges, parses the individual charges
    and returns a list of Charge objects.
    :param text - the text containing both distribution and supply charges.
    :returns A list of Charge objects representing the charges from the bill
    """
    charge_names_map = _get_charge_names_map()

    # in pepco bills, supply and distribution charges are separate
    distribution_charges_exp = r'Distribution Services:(.*?)(Status of your Deferred|Page)'
    supply_charges_exp = r'Transmission Services\:(.*?)Energy Usage History'
    dist_text = re.search(distribution_charges_exp, text).group(1)
    supply_text = re.search(supply_charges_exp, text).group(1)

    # regexes for individual charges
    exp_name = r'([A-Z][A-Za-z \(\)]+?)' # Letters, spaces, and parens (but starts with capital letter)
    exp_stuff = r'(?:(?:Includes|at\b|\d).*?)?' # stuff in between the name and value, like the per-unit rate
    exp_value = r'(\d[\d\.]*)' # The actual number we want
    exp_lookahead = r'(?=[A-Z]|$)' # The next charge name will begin with a capital letter.
    charge_exp = re.compile(exp_name + exp_stuff + exp_value + exp_lookahead)

    def process_charge(p, ct):
        name = p[0]
        value = float(p[1])
        rsi_binding = _get_rsi_binding_from_name(charge_names_map, name)
        return Charge(rsi_binding, name=name, target_total=float(value),
            type=ct, unit='kWh')

    charges = []
    for charge_text, charge_type in [(dist_text, Charge.DISTRIBUTION), (supply_text, Charge.SUPPLY)]:
        charges.extend([process_charge(c, charge_type) for c in charge_exp.findall(charge_text)])

    return charges

# Currently rate class is extracted as string, and passed to
# Applier.set_rate_class(bill, name). Not sure if we still need this
# function, which does not take into account bill utility id

# def convert_rate_class(text):
#     s = Session()
#     q = s.query(RateClass).filter(RateClass.name == text)
#     try:
#         return q.one()
#     except NoResultFound:
#         # TODO fill in fields correctly
#         return RateClass(name=text)

def convert_address(text):
    '''
    Given a string containing an address, parses the address into an Address object in the database.
    '''
    # matches city, state, and zip code
    regional_exp = r'([\w ]+),?\s+([a-z]{2})\s+(\d{5}(?:-\d{4})?)'
    # for attn: or C/O lines in billing addresses
    addressee_attn_exp = r"attn:?\s*(.*)"
    addressee_co_exp = r"(C/?O:?\s*.*)$"
    # A PO box, or a line that starts with a number
    street_exp = r"^(\d+.*?$|PO BOX \d+)"

    addressee = city = state = street = postal_code = None
    lines = re.split("\n+", text, re.MULTILINE)

    # Addresses have an uncertain number (usually 1 or 2) of addressee lines
    # The last two lines are always street and city, state, zip code.
    # However, the last two lines are sometimes switched by PDF extractors
    # This especially happens with service addresses
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # if it a po box or starts with a number, this line is a street address
        match = re.search(street_exp, line, re.IGNORECASE)
        if match:
            street = match.group(1)
            continue
        # check if this line contains city/state/zipcode
        match = re.search(regional_exp, line, re.IGNORECASE)
        if match:
            city, state, postal_code = match.groups()
            continue
        # if line has "attn:" or "C/O" in it, it is part of addresse.
        match = re.search(addressee_attn_exp, line, re.IGNORECASE)
        if match:
            if addressee is None:
                addressee = ""
            addressee += match.group(1) + " "
            continue
        match = re.search(addressee_co_exp, line, re.IGNORECASE)
        if match:
            if addressee is None:
                addressee = ""
            addressee += match.group(1) + " "
            continue

        # if none of the above patterns match, assume that this line is the
        # addressee
        if addressee is None:
            addressee = ""
        addressee += line + " "

    if addressee is not None:
        addressee = addressee.strip()
    return Address(addressee=addressee, street=street, city=city,
        state=state, postal_code=postal_code)

def convert_supplier(text):
    s = Session()
    q = s.query(Supplier).filter(Supplier.name == text)
    try:
        return q.one()
    except NoResultFound:
        # TODO fill in fields correctly
        raise ConversionError('Could not find supplier with name "%s"' % text)