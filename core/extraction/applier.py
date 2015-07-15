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


