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
from core.model import Session, RateClass, Utility, Charge, Address
from core.pricing import FuzzyPricingModel
from core.utilbill_loader import UtilBillLoader
from exc import ApplicationError


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

    CHARGES = 'charges'
    END = 'end'
    ENERGY = 'energy'
    NEXT_READ = 'next read'
    RATE_CLASS = 'rate class'
    START = 'start'

    # values must be applied in a certain order because some are needed in
    # order to apply others (e.g. rate class is needed for energy and charges)
    KEYS = OrderedDict([
        (START, model.UtilBill.period_start),
        (END, model.UtilBill.period_end),
        (NEXT_READ, model.UtilBill.set_next_meter_read_date),
        (RATE_CLASS, set_rate_class.__func__),
        (ENERGY, model.UtilBill.set_total_energy),
        (CHARGES, set_charges.__func__),
    ])
    # TODO:
    # target_total (?)
    # supplier
    # utility (could be determined by layout itself)

    # Getters for each applier key, to get the corresponding field value from
    #  a utility bill.
    GETTERS = {
        CHARGES: lambda b: b.charges,
        END: lambda b: b.period_end,
        ENERGY: lambda b: b.get_total_energy(),
        NEXT_READ: lambda b: b.next_meter_read_date,
        RATE_CLASS: lambda b: b.rate_class,
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



def convert_wg_charges_std(text):
    """Function to convert a string containing charges from a particular
    Washington Gas bill format into a list of Charges. There might eventually
    be many of these.
    """
    # TODO: it's bad to do a query in here. also, when there are many of
    # these functions, this creates duplicate code both for loading the name map
    # and for using it to convert names into rsi_bindings. it probably should
    # be an argument.
    charge_name_map = Session().query(Utility).filter_by(name='washington gas').one().charge_name_map
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

    #read charges backwards, because WG bills include previous bill amounts at top of table
    charge_values_lines = charge_values_lines[::-1]
    charge_data = [(taxes_charge_names[::-1], Charge.DISTRIBUTION),
        (supply_charge_names[::-1], Charge.SUPPLY),
        (dist_charge_names[::-1], Charge.DISTRIBUTION)]

    def process_charge(name, value, ct):
        rsi_binding = charge_name_map.get(name, name.upper().replace(' ', '_'))
        return Charge(rsi_binding, name=name, target_total=float(value), type=ct)
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
    #reverse list, remove last item ('Total Current Washington Gas Charges')
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
    charge_name_map = Session().query(Utility).filter_by(
        name='washington gas').one().charge_name_map
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
    #read charges backwards, because WG bills include previous bill amounts at top of table
    charge_values_names = charge_values_names[::-1]
    charge_data = [(taxes_charge_names[::-1], Charge.DISTRIBUTION),
        (supply_charge_names[::-1], Charge.SUPPLY),
        (dist_charge_names[::-1], Charge.DISTRIBUTION)]

    def process_charge(name, value, ct):
        rsi_binding = charge_name_map.get(name, name.upper().replace(' ', '_'))
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
    Given text output from a pepco utility bill PDF that contains supply/distribution/etc charges, parses the individual charges
    and returns a list of Charge objects.
    :param text - the text containing both distribution and supply charges.
    :returns A list of Charge objects representing the charges from the bill
    """
    #TODO deal with external suppliers
    #TODO find a better method for categorizing charge names
    charge_name_map = Session().query(Utility).filter_by(
        name='pepco').one().charge_name_map


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
        rsi_binding = charge_name_map.get(name, name.upper().replautce(' ', '_'))
        return Charge(rsi_binding, name=name, target_total=float(value), type=ct)

    charges = []
    charge_data = [(dist_charges_names, Charge.DISTRIBUTION), (supply_charges_names, Charge.SUPPLY), (trans_charges_names_clean, Charge.DISTRIBUTION)]
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

    charge_name_map = Session().query(Utility).filter_by(name='pepco').one().charge_name_map

    #in pepco bills, supply and distribution charges are separate
    distribution_charges_exp = r'Distribution Services:(.*?)(Status of your Deferred|Page)'
    supply_charges_exp = r'Transmission Services\:(.*?)Energy Usage History'
    dist_text = re.search(distribution_charges_exp, text).group(1)
    supply_text = re.search(supply_charges_exp, text).group(1)

    #regexes for individual charges
    exp_name = r'([A-Z][A-Za-z \(\)]+?)' #Letters, spaces, and parens (but starts with capital letter)
    exp_stuff = r'(?:(?:Includes|at\b|\d).*?)?' #stuff in between the name and value, like the per-unit rate
    exp_value = r'(\d[\d\.]*)' # The actual number we want
    exp_lookahead = r'(?=[A-Z]|$)' # The next charge name will begin with a capital letter.
    charge_exp = re.compile(exp_name + exp_stuff + exp_value + exp_lookahead)

    def process_charge(p, ct):
        name = p[0]
        value = float(p[1])
        rsi_binding = charge_name_map.get(name, name.upper().replace(' ', '_'))
        return Charge(rsi_binding, name=name, target_total=float(value), type=ct)

    charges = []
    for charge_text, charge_type in [(dist_text, Charge.DISTRIBUTION), (supply_text, Charge.SUPPLY)]:
        charges.extend([process_charge(c, charge_type) for c in charge_exp.findall(charge_text)])

    return charges


def convert_rate_class(text):
    s = Session()
    q = s.query(RateClass).filter(RateClass.name == text)
    try:
        return q.one()
    except NoResultFound:
        #TODO fill in fields correctly
        return RateClass(name=text)
