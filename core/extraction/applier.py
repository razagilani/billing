"""Code related to applying data extracted from utility bill files to UtilBill
objects so they can be stored in the database. Everything that depends
specifically on the UtilBill class should go here.
"""
from collections import OrderedDict
from datetime import date

from abc import ABCMeta
from dateutil.relativedelta import relativedelta
import numpy
from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.exc import NoResultFound

from core.model import Session, RateClass, UtilBill
import core.model.utilbill
from core.pricing import FuzzyPricingModel
from exc import ApplicationError
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
        utilbill.validation_state = validation_state
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

    # minimum allowable date for a field
    # max date is date.today(), which can't easily be declared as a constant
    MIN_DATE = date(2000, 1, 1)

    # max expected amounts for total energy and price
    MAX_PRICE  = 1000000
    MAX_ENERGY = 1000000

    # VALIDATION FUNCTIONS
    # These take a utility bill, a list of bills in the same utility account,
    #  and a value.
    # The functions return an element in self.VALIDATION_STATES, depending on
    #  the result of the validation.

    @staticmethod
    def _set_bill_state_if_unprocessed(bill, state, checkworst=True):
        """
        Checks if a bill is unprocessed, and then sets its validation_state.
        If checkworst is True (it is by default), then the bill's state is
        only modified if the new state is worst.
        """
        from billentry.billentry_model import BEUtilBill
        if checkworst:
            state = Validator.worst_validation_state([state,
                bill.validation_state])
        if not (isinstance(bill, BEUtilBill) and bill.is_entered()):
                    bill.validation_state = state

    @staticmethod
    def _check_date_bounds(date, start, end):
        """ Checks if a date is within bounds, inclusive. """
        return start <= date <= end

    @staticmethod
    def _overlaps_bill_period(bill, date):
        """ Checks if a date is within the period of a bill. """
        if bill.period_start is None or bill.period_end is None:
            return False
        return bill.period_start <= date < bill.period_end

    @staticmethod
    def _check_numerical_value(value, max, other_values=None, dev_ratio=None,
                               max_stdev=None):
        """
        Performs a check on a numerical value. The value is checked to be
        non-negative and not greater than the maximum.
        If a sample of other values is provided, the mean is taken and the
        value is checked not to deviate too much frmo the mean.
        :param value: The value to be checked
        :param max: The maximum allowable value
        :param other_values: A sample of other values
        :param dev_ratio: The max allowable ratio (value - mean)/mean
        :param max_stdev: The max number of standard deviations the value can
                          vary from the mean.
        :return: True if the value passed all the checks, false otherwise.
        """
        if value < 0 or value > max:
            return False
        if other_values is not None and len(other_values):
            mean = sum(other_values) / len(other_values)
            if max_stdev is not None and len(other_values) > 5:
                stdev = numpy.std(other_values, axis=0)
                if stdev == 0:
                    return value == mean
                return abs(float(value - mean)) / stdev <= max_stdev
            elif dev_ratio is not None:
                if mean == 0:
                    return value == mean
                return abs(float(value - mean)) / mean <=  dev_ratio
        return True

    @staticmethod
    def _get_previous_bill(bill, other_bills):
        """
        Given a bill with a non-null period_end, returns the utility bill in
        other_bills that is the most recent previous bill.
        Raises ValueError if bill has no period_end, and if there is no
        previous bill, None is returned.
        """
        if bill.period_end is None:
            raise ValueError("Bill's period_end is None, can't get previous "
                             "bill")
        # sort bills from most recent to earliest
        sorted_bills = sorted(other_bills, key=lambda b: b.period_end, \
            reverse=True)
        old_bills = filter(lambda b: b.period_end is not None and
                                     b.period_end<bill.period_end, sorted_bills)
        if len(old_bills) == 0:
            return None
        return old_bills[0]

    @staticmethod
    def validate_end(utilbill, bills_in_account, value):
        """ Validates a bill's end date by checking it against absolute
        min/max bounds, by comparing it to the start date, and by checking
        for overlap with other bills' end dates. """

        # check end date min / max values
        if not Validator._check_date_bounds(value, Validator.MIN_DATE,
                date.today()):
            return UtilBill.FAILED

        # check this bill's period is a reasonable length
        if utilbill.period_start is not None and not 20 < (value -
                utilbill.period_start).days < 40:
            return UtilBill.FAILED

        # Check overlap with other bills
        has_overlap = False
        for b in bills_in_account:
            # check for overlaps / short gaps with other bills
            if b.period_end is None:
                continue
            if Validator._overlaps_bill_period(b, value) or abs(value -
                    b.period_end).days < 20:
                has_overlap = True
                Validator._set_bill_state_if_unprocessed(b, UtilBill.FAILED)
        if has_overlap:
            return UtilBill.FAILED

        return UtilBill.SUCCEEDED

    @staticmethod
    def validate_start(utilbill, bills_in_account, value):
        """ Validates a bill's start date by checking it against absolute
        min/max bounds, by comparing it to the end date, and by checking
        for overlap with other bills' start dates. """

        # check start date min / max values
        if not Validator._check_date_bounds(value, Validator.MIN_DATE,
                date.today()):
            return UtilBill.FAILED

        # check this bill's period is a reasonable length
        if utilbill.period_end is not None and not 20 < (utilbill.period_end -
                value).days < 40:
            return UtilBill.FAILED

        # Check overlap with other bills
        has_overlap = False
        for b in bills_in_account:
            # check for overlaps / short gaps with other bills
            if b.period_start is None:
                continue
            if Validator._overlaps_bill_period(b, value) or abs(value -
                    b.period_start).days < 20:
                has_overlap = True
                Validator._set_bill_state_if_unprocessed(b, UtilBill.FAILED)
        if has_overlap:
            return UtilBill.FAILED

        return UtilBill.SUCCEEDED

    @staticmethod
    def validate_next_read(utilbill, bills_in_account, value):
        """ Validate a bill's next meter read. Checks that the date is within
        absolute bounds, that it is not too close to the current bill's
        period_end, and that it is not too close to other bill's
        next_meter_read. The last check returns REVIEW instead of FAIL,
        since next_meter_reads tend to be more estimated than exact dates.
        """

        # check next read date min / max values (next read date can be up to
        # one month in the future)
        if not Validator._check_date_bounds(value, Validator.MIN_DATE,
                        date.today() + relativedelta(months=1)):
            return UtilBill.FAILED

        if utilbill.period_end is not None and not 20 < (value -
                utilbill.period_end).days < 40:
            return UtilBill.FAILED

        # Check overlap with other bills' next meter read date. These can be
        # estimates, so mark discrepancies as REVIEW instead of FAILED
        has_overlap = False
        for b in bills_in_account:
            # check for short gaps with other bills' next read dates.
            if b.next_meter_read_date is None:
                continue
            if abs(value - b.next_meter_read_date).days < 20:
                has_overlap = True
                new_bill_state = Validator.worst_validation_state([
                    b.validation_state, UtilBill.REVIEW])
                Validator._set_bill_state_if_unprocessed(b, UtilBill.REVIEW)
        if has_overlap:
            return UtilBill.REVIEW

        return UtilBill.SUCCEEDED

    @staticmethod
    def validate_billing_address(utilbill, bills_in_account, value):
        """ Validates billing address by making sure it's a real address,
        and then checking if previous bills have a similar billing address.
        """
        # TODO validate address w/ USPS

        if value in [b.billing_address for b in bills_in_account]:
            return UtilBill.SUCCEEDED
        else:
            return UtilBill.REVIEW

    @staticmethod
    def validate_service_address(utilbill, bills_in_account, value):
        """ Validates service address by making sure it's a real address,
        and then checking if previous bills have a similar service address.
        """
        # TODO validate address w/ USPS

        if value in [b.service_address for b in bills_in_account]:
            return UtilBill.SUCCEEDED
        else:
            return UtilBill.REVIEW

    @staticmethod
    def validate_total(utilbill, bills_in_account, value):
        """ Validates the total energy field of a bill. Checks that the value is
         within a reasonable range, and that it matches the sum of the charges
         on the bill (if the bill has charges)
        """
        if Validator._check_numerical_value(value, Validator.MAX_PRICE,
                [b.target_total for b in bills_in_account], 0.5, 2):
            numeric_check = UtilBill.SUCCEEDED
        else:
            numeric_check = UtilBill.REVIEW

        charges_check = UtilBill.SUCCEEDED
        if utilbill.charges is not None and len(utilbill.charges) > 0:
            total_charges = sum([c.target_total for c in utilbill.charges])
            if total_charges != value:
                charges_check = UtilBill.FAILED

        return Validator.worst_validation_state([numeric_check, charges_check])

    @staticmethod
    def validate_supplier(utilbill, bills_in_account, value):
        """ Check if a bill's supplier matches the previous bill's supplier.
        """
        # get previous bill, if possible:
        prev_bill_check = UtilBill.REVIEW
        if utilbill.period_end is not None:
            prev_bill = Validator._get_previous_bill(utilbill, bills_in_account)
            if prev_bill is not None and value == prev_bill.supplier:
                prev_bill_check = UtilBill.SUCCEEDED

        # Don't know if necessaru, as function returns UtilBill.REVIEW anyway
        # # check that supplier is an existing supplier
        # s = Session()
        # if value not in s.query(Supplier).all():
        #     return UtilBill.REVIEW

        return Validator.worst_validation_state([prev_bill_check])

    @staticmethod
    def validate_rate_class(utilbill, bills_in_account, value):
        """ Check if a rate class matches the previous bill's rate class,
        and if it belongs to the same utility as the bill.
        """
        # get previous bill, if possible:
        prev_bill_check = UtilBill.REVIEW
        if utilbill.period_end is not None:
            prev_bill = Validator._get_previous_bill(utilbill, bills_in_account)
            if prev_bill is not None and  value == prev_bill.rate_class:
                prev_bill_check = UtilBill.SUCCEEDED

        # check that rate class is in the same utility as bill
        if value.utility_id == utilbill.utility_id:
            utility_check = UtilBill.SUCCEEDED
        else:
            utility_check = UtilBill.REVIEW

        return Validator.worst_validation_state([prev_bill_check, utility_check])

    @staticmethod
    def validate_energy(utilbill, bills_in_account, value):
        """ Validates the total energy field of a bill. Checks that the value is
         within a reasonable range
        """
        if Validator._check_numerical_value(value, Validator.MAX_ENERGY,
                [b.get_total_energy() for b in bills_in_account], 0.5, 2):
            return UtilBill.SUCCEEDED
        else:
            return UtilBill.REVIEW

    @staticmethod
    def validate_charges(utilbill, bills_in_account, value):
        pass

    # Map from an applier key (representing a field on a bill) to a function
    # to validate it.
    KEYS = OrderedDict([
        (UtilBillApplier.START, validate_start.__func__),
        (UtilBillApplier.END, validate_end.__func__),
        (UtilBillApplier.NEXT_READ, validate_next_read.__func__),
        (UtilBillApplier.BILLING_ADDRESS, validate_billing_address.__func__),
        (UtilBillApplier.SERVICE_ADDRESS, validate_service_address.__func__),
        (UtilBillApplier.SUPPLIER, validate_supplier.__func__),
        (UtilBillApplier.TOTAL, validate_total.__func__),
        (UtilBillApplier.RATE_CLASS, validate_rate_class.__func__),
        (UtilBillApplier.ENERGY, validate_energy.__func__),
        (UtilBillApplier.CHARGES, validate_charges.__func__),
    ])


    @staticmethod
    def worst_validation_state(states):
        """
        Given a set of states, return the worst validation state.
        This is based on the ordering in UtilBill.VALIDATION_STATES,
        which goes from worst to best.
        If an empty list of states is given, ValueError is raised.
        """
        for vs in UtilBill.VALIDATION_STATES:
            if vs in states:
                return vs
        raise ValueError("empty list passed to worst_validation_state")

    @staticmethod
    def validate_bill(utilbill, keys=KEYS.keys()):
        """
        Validate a bill, using a specific set of fields. By default,
        all fields in UtilBill.KEYS are used.
        Returns the validation state for the bill, which is the worst
        validation state returned by any of the fields.
        e.g. if one field fails, the whole bill fails.
        """
        s = Session()
        bills_in_account = s.query(UtilBill).filter(
            UtilBill.utility_account_id == utilbill.utility_account_id,
            UtilBill.id != utilbill.id).all()

        bill_validation = UtilBill.SUCCEEDED
        for (applier_key, func) in Validator.KEYS.iteritems():
            if applier_key in keys:
                value = UtilBillApplier.GETTERS[applier_key](utilbill)
                field_validation = func(utilbill, bills_in_account,
                    value)

                # update bill validation state with worst validation state
                bill_validation = Validator.worst_validation_state([
                    bill_validation, field_validation])

        return bill_validation