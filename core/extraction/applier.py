"""Code related to applying data extracted from utility bill files to UtilBill
objects so they can be stored in the database. Everything that depends
specifically on the UtilBill class should go here.
"""
from abc import ABCMeta
from collections import OrderedDict

from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.exc import NoResultFound

from core.model import Session, RateClass, UtilBill
import core.model.utilbill
from core.pricing import FuzzyPricingModel
from exc import ApplicationError, ConversionError, ValidationError
from core.utilbill_loader import UtilBillLoader


class Applier(object):
    __metaclass__ = ABCMeta

    def __init__(self, keys):
        self.keys = keys

    def apply(self, extractor, *args):
        raise NotImplementedError

    def get_keys(self):
        """:return: list of keys (strings) in the order they should be
        applied. (Not necessarily the 'KEYS' of the default Applier.)
        """
        return self.keys.keys()


class UtilBillApplier(Applier):
    """Applies extracted values to attributes of UtilBill. There's no
    instance-specific state so only one instance is needed.

    To apply values to something other than a UtilBill, a superclass could be
    created that includes the non-UtilBill specific parts, and other subclasses
    of it would have different 'KEYS' and a different implementation of 'apply'.
    """
    @staticmethod
    def set_rate_class(bill, rate_class_name):
        """
        Given a bill and a rate class name, this function sets the rate class
        of the bill. If the name corresponds to an existing rate class in the
        database, then the existing rate class is used. Otherwise, a new rate
        class object is created.
        Note: This function uses the default service for all bills.
        :param bill: A UtilBill object
        :param rate_class_name:  A string, the name of the rate class
        """
        rate_class_name = rate_class_name.strip()
        s = Session()
        bill_util = bill.get_utility()
        if bill_util is None:
            raise ApplicationError(
                "Unable to set rate class for bill id %s: utility is unknown" %
                bill_util.id)
        q = s.query(RateClass).filter(RateClass.name == rate_class_name,
                                      RateClass.utility == bill_util)
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
    TOTAL = 'total'
    RATE_CLASS = 'rate class'
    SERVICE_ADDRESS = 'service address'
    START = 'start'
    SUPPLIER = 'supplier'

    # values must be applied in a certain order because some are needed in
    # order to apply others (e.g. rate class is needed for energy and charges)
    KEYS = OrderedDict([
        (START, core.model.UtilBill.period_start),
        (END, core.model.UtilBill.period_end),
        (NEXT_READ, core.model.UtilBill.set_next_meter_read_date),
        (BILLING_ADDRESS, core.model.UtilBill.billing_address),
        (SERVICE_ADDRESS, core.model.UtilBill.service_address),
        (SUPPLIER, core.model.UtilBill.set_supplier),
        (TOTAL, core.model.UtilBill.target_total),
        (RATE_CLASS, set_rate_class.__func__),
        (ENERGY, core.model.UtilBill.set_total_energy),
        (CHARGES, set_charges.__func__),
    ])
    # TODO:
    # target_total (?)
    # supplier
    # utility (could be determined by layout itself)

    # Getters for each applier key, to get the corresponding field value from
    # a utility bill.
    GETTERS = {
        BILLING_ADDRESS: lambda b: b.billing_address,
        CHARGES: lambda b: b.charges,
        END: lambda b: b.period_end,
        ENERGY: lambda b: b.get_total_energy(),
        NEXT_READ: lambda b: b.next_meter_read_date,
        TOTAL: lambda b: b.target_total,
        RATE_CLASS: lambda b: b.rate_class,
        SERVICE_ADDRESS: lambda b: b.service_address,
        START: lambda b: b.period_start,
        SUPPLIER: lambda b: b.supplier
    }

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls(cls.KEYS)
        return cls._instance

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
                execute = lambda: attr(utilbill, value)
            elif hasattr(utilbill, attr.__name__):
                method = getattr(utilbill, attr.__name__)
                # method of UtilBill
                execute = lambda: method(value)
            else:
                # other callable. it must take a UtilBill and the value to
                # apply.
                execute = lambda: attr(utilbill, value)
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
            execute = lambda: setattr(utilbill, attr_name, value)

        # do it
        s = Session()
        try:
            execute()
            # catch database errors here too
            s.flush()
        except Exception as e:
            raise ApplicationError('%s: %s' % (e.__class__, e.message))
        finally:
            s.flush()

    def apply_values(self, extractor, utilbill, bill_file_handler):
        """Update attributes of the given bill with data extracted from its
        file. Return value can be used to compare success rates of different
        Extractors.
        :param extractor: Extractor
        :param utilbill: UtilBill
        :param bill_file_handler: BillFileHandler to get files for UtilBills.
        :return number of fields successfully extracted and applied (integer),
        dictionary of key -> Exceptions (which can be either ExtractionErrors or
        ApplicationErrors)
        """
        good, errors = extractor.get_values(utilbill, bill_file_handler)
        success_keys = []
        success_count = 0
        for key in self.get_keys():
            try:
                value = good[key]
            except KeyError:
                # missing key is OK (but unrecognized key is an error)
                continue
            try:
                self.apply(key, value, utilbill)
            except ApplicationError as error:
                errors[key] = error
            else:
                success_count += 1
                success_keys.append(key)
        validation_state = Validator.validate_bill(utilbill, success_keys)
        # TODO add validatoin_state column to UtilBill table
        for key in set(good.iterkeys()) - set(self.get_keys()):
            errors[key] = ApplicationError('Unknown key "%s"' % key)
        return success_count, errors

class Validator:
    """
    A class for validating extracted data from utility bills. Validation
    involves making sure that extracted values make sense (e.g. start date
    before end date, dates after Jan. 1900) and that they are not too unusual
    for a given utility account.
    Bills can be marked FAILED, REVIEW, or SUCCEEDED depending on whether the
    data for a bill is incorrect, unusual, or valid.
    """

    # This represents different states for validation of a bill.
    # FAILED - validation has failed, and the extracted data is incorrect
    # REVIEW - the extracted data is unusual/irregular, and should be
    #          reviewed by a human
    # SUCCEEDED - the extracted data is valid, and does not need to be reviewed.
    FAILED = 'failed'
    REVIEW = 'review'
    SUCCEEDED = 'succeeded'
    # the ordering here is important, states go from worst to best.
    VALIDATION_STATES = [FAILED, REVIEW, SUCCEEDED]

    # VALIDATION FUNCTIONS
    # These take a utility bill, a list of bills in the same utility account,
    #  and a value.
    # The functions return an element in self.VALIDATION_STATES, depending on
    #  the
    @staticmethod
    def validate_start(self, utilbill, bills_in_account, value):
        pass

    @staticmethod
    def validate_end(self, utilbill, bills_in_account, value):
        pass

    @staticmethod
    def validate_next_read(self, utilbill, bills_in_account, value):
        pass

    @staticmethod
    def validate_billing_address(self, utilbill, bills_in_account, value):
        pass

    @staticmethod
    def validate_service_address(self, utilbill, bills_in_account, value):
        pass

    @staticmethod
    def validate_total(self, utilbill, bills_in_account, value):
        pass

    @staticmethod
    def validate_supplier(self, utilbill, bills_in_account, value):
        pass

    @staticmethod
    def validate_rate_class(self, utilbill, bills_in_account, value):
        pass

    @staticmethod
    def validate_energy(self, utilbill, bills_in_account, value):
        pass

    @staticmethod
    def validate_charges(self, utilbill, bills_in_account, value):
        pass

    # Map from an applier key (representing a field on a bill) to a function
    # to validate it.
    KEYS = OrderedDict([
        (UtilBillApplier.START, validate_start),
        (UtilBillApplier.END, validate_end),
        (UtilBillApplier.NEXT_READ, validate_next_read),
        (UtilBillApplier.BILLING_ADDRESS, validate_billing_address),
        (UtilBillApplier.SERVICE_ADDRESS, validate_service_address),
        (UtilBillApplier.SUPPLIER, validate_supplier),
        (UtilBillApplier.TOTAL, validate_total),
        (UtilBillApplier.RATE_CLASS, validate_rate_class),
        (UtilBillApplier.ENERGY, validate_energy),
        (UtilBillApplier.CHARGES, validate_charges),
    ])


    @staticmethod
    def worst_validation_state(states):
        """
        Given a set of states, return the worst validation state.
        This is based on the ordering in Validator.VALIDATION_STATES,
        which goes from worst to best.
        """
        for vs in Validator.VALIDATION_STATES:
            if vs in states:
                return vs

    @staticmethod
    def validate_bill(utilbill, keys=KEYS.keys()):
        """
        Validate a bill, using a specific set of fields. By default,
        all fields in Validator.KEYS are used.
        Returns the validation state for the bill, which is the worst
        validation state returned by any of the fields.
        e.g. if one field fails, the whole bill fails.
        """
        s = Session()
        bills_in_account = s.query(UtilBill).filter(
            UtilBill.utility_account_id == utilbill.utility_account_id,
            UtilBill.id != utilbill.id).all()

        bill_validation = Validator.SUCCEEDED
        for (applier_key, func) in Validator.KEYS.iteritems():
            if applier_key in keys:
                value = UtilBillApplier.GETTERS[applier_key](utilbill)
                field_validation = func(utilbill, bills_in_account, value)

                # update bill validation state with worst validation state
                bill_validation = Validator.worst_validation_state([
                    bill_validation, field_validation])

        return bill_validation