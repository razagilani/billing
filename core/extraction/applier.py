"""Code related to applying data extracted from utility bill files to UtilBill
objects so they can be stored in the database. Everything that depends
specifically on the UtilBill class should go here.
"""
from collections import OrderedDict
import re
from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.exc import NoResultFound
from core import model
from core.model import Session, RateClass, Utility, Address
from core.model.utilbill import Charge
import core.model.utilbill
from core.pricing import FuzzyPricingModel
from exc import ApplicationError, ConversionError
from core.utilbill_loader import UtilBillLoader


class Applier(object):
    """Applies extracted values to attributes of UtilBill. There's no
    instance-specific state so only one instance is needed.

    To apply values to something other than a UtilBill, a superclass could be
    created that includes the non-UtilBill specific parts, and other subclasses
    of it would have different 'KEYS' and a different implementation of 'apply'.
    """
    @staticmethod
    def set_rate_class(bill, rate_class_name):
        """
        Given a bill and a rate class name, this function sets the rate class of the bill.
        If the name corresponds to an existing rate class in the database, then the existing rate class is used.
        Otherwise, a new rate class object is created.
        Note: This function uses the default service for all bills.
        :param bill: A UtilBill object
        :param rate_class_name:  A string, the name of the rate class
        """
        rate_class_name = rate_class_name.strip()
        s = Session()
        bill_util = bill.get_utility()
        if bill_util is None:
            raise ApplicationError("Unable to set rate class for bill id %s: utility is unknown" % bill_util.id)
        q = s.query(RateClass).filter(RateClass.name == rate_class_name, RateClass.utility == bill_util)
        try:
            rate_class = q.one()
        except NoResultFound:
            rate_class = RateClass(utility=bill_util, name=rate_class_name)
        bill.set_rate_class(rate_class)

    @staticmethod
    def set_charges(bill, charges):
        """Special function to apply a list of charges, because the a unit is
        required and may not be known. If possible, get rid of this function.
        """
        unit = bill.get_total_energy_unit()

        # unit will not be known if rate class is not set
        if unit is None:
            unit = 'kWh'

        # use FuzzyPricingModel to find nearby occurrences of the same charge
        # in bills with the same rate class/supplier/supply group, to copy
        # the formula from them. this will only work if the rate
        # class/supplier/supply group and period dates are known (if
        # extracted they must be applied before charges).
        fpm = FuzzyPricingModel(UtilBillLoader())

        # charges must be associated with UtilBill for
        # get_closest_occurrence_of_charge to work below
        bill.charges = charges

        for charge in charges:
            charge.unit = unit

            # if there is a "closest occurrence", always copy the formula
            # from it, but only copy the rate if was not already extracted
            other_charge = fpm.get_closest_occurrence_of_charge(charge)
            if other_charge is not None:
                charge.formula = other_charge.formula
                if charge.rate is None:
                    charge.rate = other_charge.rate

    BILLING_ADDRESS = 'billing address'
    CHARGES = 'charges'
    END = 'end'
    ENERGY = 'energy'
    NEXT_READ = 'next read'
    PERIOD_TOTAL = 'period total'
    RATE_CLASS = 'rate class'
    SERVICE_ADDRESS = 'service address'
    START = 'start'

    # values must be applied in a certain order because some are needed in
    # order to apply others (e.g. rate class is needed for energy and charges)
    KEYS = OrderedDict([
        (START, core.model.utilbill.UtilBill.period_start),
        (END, core.model.utilbill.UtilBill.period_end),
        (NEXT_READ, core.model.utilbill.UtilBill.set_next_meter_read_date),
        (BILLING_ADDRESS, model.UtilBill.billing_address),
        (SERVICE_ADDRESS, model.UtilBill.service_address),
        (PERIOD_TOTAL, model.UtilBill.target_total),
        (RATE_CLASS, set_rate_class.__func__),
        (ENERGY, core.model.utilbill.UtilBill.set_total_energy),
        (CHARGES, set_charges.__func__),
    ])
    # TODO:
    # target_total (?)
    # supplier
    # utility (could be determined by layout itself)

    # Getters for each applier key, to get the corresponding field value from
    #  a utility bill.
    GETTERS = {
        BILLING_ADDRESS: lambda b: b.billing_address,
        CHARGES: lambda b: b.charges,
        END: lambda b: b.period_end,
        ENERGY: lambda b: b.get_total_energy(),
        NEXT_READ: lambda b: b.next_meter_read_date,
        PERIOD_TOTAL: lambda b: b.target_total,
        RATE_CLASS: lambda b: b.rate_class,
        SERVICE_ADDRESS: lambda b: b.service_address,
        START: lambda b: b.period_start,
    }

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls(cls.KEYS)
        return cls._instance

    def __init__(self, keys):
        self.keys = keys

    def get_keys(self):
        """:return: list of keys (strings) in the order they should be
        applied. (Not necessarily the 'KEYS' of the default Applier.)
        """
        return self.keys.keys()

    def apply(self, key, value, utilbill):
        """Set the value of a UtilBill attribute. Raise ApplicationError if
        anything goes wrong.
        :param key: one of KEYS (determines which UtilBill attribute gets
        the value)
        :param value: extracted value to be applied
        :param utilbill: UtilBill
        """
        attr = self.keys.get(key)
        if attr is None:
            raise ApplicationError('Unknown key "%s"' % key)

        # figure out how to apply the value based on the type of the attribute
        if callable(attr):
            if hasattr(self.__class__, attr.__name__):
                # method of this class (takes precedence over UtilBill method
                # with the same name)
                apply = lambda: attr(utilbill, value)
            elif hasattr(utilbill, attr.__name__):
                method = getattr(utilbill, attr.__name__)
                # method of UtilBill
                apply = lambda: method(value)
            else:
                # other callable. it must take a UtilBill and the value to
                # apply.
                apply = lambda: attr(utilbill, value)
        else:
            # non-method attribute
            if isinstance(attr.property, RelationshipProperty):
                # relationship attribute
                attr_name = attr.property.key
            elif isinstance(attr, InstrumentedAttribute):
                # regular column atttribute
                attr_name = attr.property.columns[0].name
                # catch type error before the value gets saved in db
                the_type = attr.property.columns[0].type.python_type
                if not isinstance(value, the_type):
                    raise ApplicationError('Expected type %s, got %s %s' % (
                        the_type, type(value), value))
            else:
                raise ApplicationError(
                    "Can't apply %s to %s: unknown attribute type %s" % (
                        value, attr, type(attr)))
            apply = lambda: setattr(utilbill, attr_name, value)

        # do it
        s = Session()
        try:
            apply()
            # catch database errors here too
            s.flush()
        except Exception as e:
            raise ApplicationError('%s: %s' % (e.__class__, e.message))
        finally:
            s.flush()

def convert_table_charges(rows):
    """
    Converts a list of charges extracted from a TableField.
    """
    #TODO get charge name map by utility

    num_format = r"[\d,.]+"
    # this is based off the units currently in the charge table in the database.
    # these will probably have to be updated
    unit_format = r"kWd|kWh|dollars|th|therms|BTU|MMBTU|\$"
    # matches text of the form <quantity> <unit> x <rate>
    #   e.g. 1,362.4 TH x .014
    register_format = r"(%s)\s*(%s)\s*x\s*(%s)" % (num_format, unit_format,
    num_format)

    def convert_unit(unit):
        """
        Convert units found in bills to standardized formats.
        """
        if unit in Charge.CHARGE_UNITS:
            return unit
        #by default, if no unit then assume dollars
        if not unit:
            return "dollars"
        if unit == "th":
            return "therms"
        if unit == "$":
            return "dollars"
        #if unit is not valid, raise an error
        raise ConversionError('unit "%s" is not in set of allowed units.' %
                              unit)

    def process_charge(row, ctype=Charge.DISTRIBUTION):
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

        #first cell in row is the name of the charge (and sometimes contains
        # rate info as well), while the last cell in row is the value of the
        # charge.
        text = row[0]
        value = row[-1]
        if not text or not value:
            raise ConversionError('Table row ("%s", "%s") contains an empty '
                                  'element.' % row)

        #set up default values
        rsi_binding = target_total = None
        rate = 0
        description = unit = ''

        # if row does not end with some kind of number, this is not a charge.
        match = re.search(num_format, value)
        if match:
            target_total = match.group(0)
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
            match = re.match(r"(.*?)\s*%s" % register_format, cell,
                re.IGNORECASE)
            if match:
                reg_quantity = match.group(2)
                reg_unit = match.group(3)
                rate = match.group(4)
                #TODO create register, formula
            # register info is often in same text box as the charge name.
            # If this is the case, separate the description from the other info.
            if i == 0:
                description = match.group(1) if match else cell

        #Get rsi binding from database, by looking for existing charges with
        # the same description.
        q = Session.query(Charge.rsi_binding).filter(
            Charge.description==description, bool(Charge.rsi_binding))
        rsi_binding = q.first()
        if rsi_binding is None:
            #TODO what to do if existing RSI binding not found?
            pass

        return Charge(description=description, unit=unit, rate=rate,
            rsi_binding=rsi_binding, type=ctype, target_total=target_total)

    # default charge type is DISTRIBUTION
    charge_type = Charge.DISTRIBUTION
    charges = []
    for i in range (0, len(rows)):
        row = rows[i]
        if not row:
            continue

        if len(row) == 1:
            #If this label is not in all caps and has no colon at the end,
            # assume it is part of the next row's charge name that got wrapped.
            if re.search(r"[a-z]", row[0]) and not re.search(":$", row[0]):
                # if the next row exists, and is an actual charge row,
                # append this current row's text to the next row's name
                if i < len(rows) - 1 and len(rows[i+1]) > 1:
                    rows[i+1][0] = row[0] + " " + rows[i+1][0]
                    continue

            #check if this row is a header for a type of charge.
            if re.search(r"suppl[iy]|generation|transmission", row[0],
                    re.IGNORECASE):
                charge_type = Charge.SUPPLY
            else:
                charge_type = Charge.DISTRIBUTION
            continue

        charges.append(process_charge(row, charge_type))
    return filter(None, charges)

def convert_address(text):
    '''
    Given a string containing an address, parses the address into an Address object in the database.
    '''
    #matches city, state, and zip code
    regional_exp = r'([\w ]+),?\s+([a-z]{2})\s+(\d{5}(?:-\d{4})?)'
    #for attn: or C/O lines in billing addresses
    addressee_attn_exp = r"attn:?\s*(.*)"
    addressee_co_exp = r"(C/?O:?\s*.*)$"
    #A PO box, or a line that starts with a number
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
        #if it a po box or starts with a number, this line is a street address
        match = re.search(street_exp, line, re.IGNORECASE)
        if match:
            street = match.group(1)
            continue
        # check if this line contains city/state/zipcode
        match = re.search(regional_exp, line, re.IGNORECASE)
        if match:
            city, state, postal_code = match.groups()
            continue
        #if line has "attn:" or "C/O" in it, it is part of addresse.
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

        #if none of the above patterns match, assume that this line is the
        # addressee
        if addressee is None:
            addressee = ""
        addressee += line + " "
    return Address(addressee=addressee, street=street, city=city, state=state,
        postal_code=postal_code)