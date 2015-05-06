import json
from datetime import datetime,date

from sqlalchemy.orm.exc import NoResultFound

from core.model import UtilBill, Address, Charge, Register, Session, \
    Supplier, Utility, RateClass, UtilityAccount, SupplyGroup
from exc import NoSuchBillException, DuplicateFileError, BillingError
from core.utilbill_loader import UtilBillLoader


ACCOUNT_NAME_REGEX = '[0-9a-z]{5}'


class UtilbillProcessor(object):
    ''''Does a mix of the following things:
    - Operations on utility bills: upload, delete, compute, regenerate charges,
    etc.
    - CRUD on child objects of UtilBill that are closely associated
    with UtilBills, like charges and registers.
    - CRUD on utilities, suppliers, rate classes.
    '''
    def __init__(self, pricing_model, bill_file_handler, logger=None):
        self.pricing_model = pricing_model
        self.bill_file_handler = bill_file_handler
        self.logger = logger
        self._utilbill_loader = UtilBillLoader()

    ############################################################################
    # methods that are actually for "processing" UtilBills
    ############################################################################

    def update_utilbill_metadata(
            self, utilbill_id, period_start=None, period_end=None, service=None,
            target_total=None, utility=None, supplier=None, rate_class=None,
            supply_group=None, processed=None, supply_choice_id=None,
            meter_identifier=None, tou=None):
        """Update various fields for the utility bill having the specified
        `utilbill_id`. Fields that are not None get updated to new
        values while other fields are unaffected.
        """
        utilbill = self._utilbill_loader.get_utilbill_by_id(utilbill_id)
        assert utilbill.utility is not None

        if processed is True:
            utilbill.check_processable()
            utilbill.processed = processed
            # since the bill has become processed no other changes to the bill
            # can be made so return the util bill without raising an error
            return utilbill
        elif processed is False:
            utilbill.processed = processed

        utilbill.check_editable()
        if tou is not None:
            utilbill.tou = tou

        if target_total is not None:
            utilbill.target_total = target_total

        if service is not None:
            utilbill.rate_class.service = service

        if supply_choice_id is not None:
            utilbill.supply_choice_id = supply_choice_id

        if supplier is not None:
            utilbill.supplier = self.get_create_supplier(supplier)

        if supply_group is not None:
            utilbill.supply_group = self.get_create_supply_group(
                supply_group, utilbill.supplier)

        if rate_class is not None:
            utilbill.rate_class = self.get_create_rate_class(
                rate_class, utilbill.utility, utilbill.get_service() if
                utilbill.get_service() is not None else 'gas')

        if utility is not None and isinstance(utility, basestring):
            utilbill.utility, new_utility = self.get_create_utility(utility)
            if new_utility:
                utilbill.rate_class = None

        if meter_identifier is not None:
            utilbill.set_total_meter_identifier(meter_identifier)

        period_start = period_start if period_start else \
            utilbill.period_start
        period_end = period_end if period_end else utilbill.period_end

        UtilBill.validate_utilbill_period(period_start, period_end)
        utilbill.period_start = period_start
        utilbill.period_end = period_end
        self.compute_utility_bill(utilbill.id)
        return  utilbill

    def _create_utilbill_in_db(self, utility_account, start=None, end=None,
                               utility=None, rate_class=None, total=0,
                               state=UtilBill.Complete, supplier=None,
                               supply_group=None):
        '''
        Returns a UtilBill with related objects (Charges and Registers
        assigned to it). Does not add anything to the session, so callers can
        do this only if no exception was raised by BillFileHandler when
        uploading the file.`
        :param utility_account:
        :param start:
        :param end:
        :param utility:
        :param rate_class:
        :param total:
        :param state:
        :param supplier:
        :return:
        '''
        # validate arguments
        UtilBill.validate_utilbill_period(start, end)

        session = Session()

        # find an existing utility bill that will provide rate class and
        # utility name for the new one, or get it from the template.
        # note that it doesn't matter if this is wrong because the user can
        # edit it after uploading.
        try:
            # previously this was filtered by service so only bills with the
            # same service could be used by predecessors. now any bill for the
            # same UtilityAccount is used, because realistically they will all
            # have the same service.
            predecessor = UtilBillLoader().get_last_real_utilbill(
                utility_account.account, end=start)
            billing_address = predecessor.billing_address
            service_address = predecessor.service_address
        except NoSuchBillException as e:
            # If we don't have a predecessor utility bill (this is the first
            # utility bill we are creating for this customer) then we get the
            # closest one we can find by time difference, having the same rate
            # class and utility.

            q = session.query(UtilBill). \
                filter_by(rate_class=utility_account.fb_rate_class). \
                filter_by(utility=utility_account.fb_utility).\
                filter_by(processed=True)

            # find "closest" or most recent utility bill to copy data from
            if start is None:
                next_ub = None
                prev_ub = q.order_by(UtilBill.period_start.desc()).first()
            else:
                next_ub = q.filter(UtilBill.period_start >= start). \
                order_by(UtilBill.period_start).first()
                prev_ub = q.filter(UtilBill.period_start <= start). \
                    order_by(UtilBill.period_start.desc()).first()
            next_distance = (next_ub.period_start - start).days if next_ub \
                else float('inf')
            prev_distance = (start - prev_ub.period_start).days if prev_ub \
                and start else float('inf')
            predecessor = None if next_distance == prev_distance == float('inf') \
                else prev_ub if prev_distance < next_distance else next_ub

            billing_address = utility_account.fb_billing_address
            service_address = utility_account.fb_service_address

        # order of preference for picking utility/supplier/rate_class: value
        # passed as an argument, same value as predecessor,
        # "fb" values from Customer
        # TODO: this is unnecessarily complicated.
        if utility is None:
            utility = getattr(predecessor, 'utility', None)
        if utility is None:
            utility = utility_account.fb_utility
        if supplier is None:
            supplier = getattr(predecessor, 'supplier', None)
        if supplier is None:
            supplier = utility_account.fb_supplier
        if rate_class is None:
            rate_class = getattr(predecessor, 'rate_class', None)
        if rate_class is None:
            rate_class = utility_account.fb_rate_class
        if supply_group is None:
            supply_group = utility_account.fb_supply_group

        new_utilbill = UtilBill(
            utility_account, utility, rate_class, supplier=supplier,
            billing_address=billing_address.clone(),
            service_address=service_address.clone(),
            period_start=start, period_end=end, target_total=total,
            date_received=datetime.utcnow(), state=state,
            supply_group=supply_group)

        new_utilbill.charges = self.pricing_model. \
            get_predicted_charges(new_utilbill)
        new_utilbill.compute_charges()

        # a register called "REG_TOTAL" should always exist because it's in
        # the rate class' register list. however, since rate classes don't yet
        # contain all the registers they should, copy any registers from the
        # predecessor to the current bill that the current bill does not already
        # have (as determined by "register_binding").
        # TODO: in the future, registers should be determined entirely by the
        # rate class, not by copying from other bills.
        for register in predecessor.registers if predecessor else []:
            if register.register_binding in (r.register_binding for r in
                                             new_utilbill.registers):
                # Since these registers were created from rate_class
                # template, and because rate_class template cannot fill in the
                # correct values for identifier and meter_identifier
                # so we need to copy these two values from corresponding
                # predecessor registers
                for r in new_utilbill.registers:
                    r.identifier = register.identifier
                    r.meter_identifier = register.meter_identifier
                continue
            new_utilbill.registers.append(
                Register(register.register_binding, unit=register.unit,
                         quantity=0, identifier=register.identifier,
                         reg_type=register.reg_type,
                         active_periods=register.active_periods,
                         meter_identifier=register.meter_identifier))
        return new_utilbill

    def upload_utility_bill(self, account, bill_file, start=None, end=None,
                            service=None, utility=None, rate_class=None,
                            total=0, state=UtilBill.Complete, supplier=None,
                            supply_group=None):
        """Uploads `bill_file` with the name `file_name` as a utility bill for
        the given account, service, and dates. If this is the newest or
        oldest utility bill for the given account and service, "estimated"
        utility bills will be added to cover the gap between this bill's period
        and the previous newest or oldest one respectively. The total of all
        charges on the utility bill may be given.

        Returns the newly created UtilBill object.

        Currently 'utility' and 'rate_class' are ignored in favor of the
        predecessor's (or template's) values; see
        https://www.pivotaltracker.com/story/show/52495771
        """
        # file-dependent validation
        if bill_file is None and state in (UtilBill.UtilityEstimated,
                                           UtilBill.Complete):
            raise ValueError(("A file is required for a complete or "
                              "utility-estimated utility bill"))
        if bill_file is not None and state == UtilBill.Estimated:
            raise ValueError("Estimated utility bills can't have a file")

        # create in database
        if utility is not None:
            utility, new_utility = self.get_create_utility(utility)
        if rate_class is not None:
            rate_class = self.get_create_rate_class(rate_class, utility, 'gas')
        if supplier is not None:
           supplier = self.get_create_supplier(supplier)
        if supply_group is not None:
            supply_group = self.get_create_supply_group(supply_group, supplier)
        session = Session()
        utility_account = session.query(UtilityAccount).filter_by(
            account=account).one()
        new_utilbill = self._create_utilbill_in_db(utility_account, start=start,
            end=end, utility=utility, rate_class=rate_class, total=total,
            state=state, supplier=supplier, supply_group=supply_group)

        # upload the file
        if bill_file is not None:
            self.bill_file_handler.upload_file_for_utilbill(new_utilbill,
                                                             bill_file)

        # adding UtilBill should also add Charges and Registers due to cascade
        session.add(new_utilbill)
        session.flush()

        return new_utilbill

    def create_utility_bill_with_existing_file(self, utility_account, utility,
                                  sha256_hexdigest, due_date=None,
                                  target_total=None, service_address=None):
        '''Create a UtilBill in the database corresponding to a file that
        has already been stored in S3.
        :param utility_account: UtilityAccount to which the new bill will
        belong.
        :param utility_guid: specifies which utility this bill is for.
        :param sha256_hexdigest: SHA-256 hash of the existing file,
        which should also be (part of) the file name and sufficient to
        determine which existing file goes with this bill.
        :param target_total: total of charges on the bill (float).
        :param service_address: service address for new utility bill (Address).
        '''
        assert isinstance(utility_account, UtilityAccount)
        assert isinstance(utility, Utility)
        assert isinstance(sha256_hexdigest, basestring) and len(
            sha256_hexdigest) == 64;
        assert isinstance(due_date, (date, type(None)))
        assert isinstance(target_total, (float, int, type(None)))
        assert isinstance(service_address, (Address, type(None)))

        if UtilBillLoader().count_utilbills_with_hash(sha256_hexdigest) != 0:
            raise DuplicateFileError('Utility bill already exists with '
                                     'file hash %s' % sha256_hexdigest)

        new_utilbill = self._create_utilbill_in_db(utility_account,
                                                   utility=utility)

        # adding UtilBill should also add Charges and Registers due to cascade
        session = Session()
        session.add(new_utilbill)
        session.flush()

        # set hexdigest of the file (this would normally be done by
        # BillFileHandler.upload_utilbill_pdf_to_s3)
        new_utilbill.sha256_hexdigest = sha256_hexdigest

        if target_total is not None:
            new_utilbill.target_total = target_total
        if service_address is not None:
            new_utilbill.service_address = service_address
        if due_date is not None:
            new_utilbill.due_date = due_date

        self.bill_file_handler.check_file_exists(new_utilbill)
        return new_utilbill

    def delete_utility_bill_by_id(self, utilbill_id):
        """Deletes the utility bill given by its MySQL id 'utilbill_id' (if

        it's not attached to a reebill) and returns the deleted state
        .UtilBill object and the path  where the file was moved (it never
        really gets deleted). This path will be None if there was no file or
        it could not be found. Raises a ValueError if the
        utility bill cannot be deleted.
        """
        session = Session()
        utility_bill = session.query(UtilBill).filter(
            UtilBill.id == utilbill_id).one()

        # don't delete a utility bill that can't be edited, i.e. is "processed".
        # every utility bill with a reebill should be processed, so it should
        # not be necessary to check whether the utility bill has a reebill here
        # (avoiding the need to use parts of the ReeBill data model outside
        # of ReeBill)
        utility_bill.check_editable()

        self.bill_file_handler.delete_file(utility_bill)

        # TODO use cascade instead if possible
        for charge in utility_bill.charges:
            session.delete(charge)
        for register in utility_bill.registers:
            session.delete(register)
        session.delete(utility_bill)

        pdf_url = self.bill_file_handler.get_url(utility_bill)
        return utility_bill, pdf_url

    def regenerate_charges(self, utilbill_id):
        """Replace the charges of the bill given by utilbill_id with new ones
        generated by the pricing model.
        """
        utilbill = self._utilbill_loader.get_utilbill_by_id(utilbill_id)
        utilbill.regenerate_charges(self.pricing_model)
        return utilbill

    def compute_utility_bill(self, utilbill_id):
        '''Updates all charges in the utility bill given by 'utilbill_id'.
        Also updates some keys in the document that are duplicates of columns
        in the MySQL table.
        '''
        utilbill = self._utilbill_loader.get_utilbill_by_id(utilbill_id)
        utilbill.compute_charges()
        return utilbill

    ############################################################################
    # CRUD methods for child objects of UtilBill
    ############################################################################

    def new_register(self, utilbill_id, **register_kwargs):
        """Creates a new register for the utility bill having the specified id
        "row" argument is a dictionary but keys other than
        "meter_id" and "register_id" are ignored.
        """
        # TODO: this code belongs inside UtilBill, if it has to exist at all
        session = Session()
        utility_bill = session.query(UtilBill).filter_by(id=utilbill_id).one()
        utility_bill.check_editable()
        # register must have a valid "register_binding" value. yes this is a
        # pretty bad way to do it.
        i = 0
        new_reg_binding = Register.REGISTER_BINDINGS[0]
        while i < Register.REGISTER_BINDINGS:
            new_reg_binding = Register.REGISTER_BINDINGS[i]
            if new_reg_binding not in (r.register_binding for r in
                                   utility_bill.registers):
                break
            i += 1
        if i == len(Register.REGISTER_BINDINGS):
            raise BillingError("No more registers can be added")

        r = Register(
            register_kwargs.get('register_binding', new_reg_binding),
            register_kwargs.get('unit', 'therms'),
            description=register_kwargs.get(
                'description',"Insert description"),
            identifier=register_kwargs.get(
                'identifier', "Insert register ID here"),
            estimated=register_kwargs.get('estimated', False),
            reg_type=register_kwargs.get('reg_type', "total"),
            active_periods=register_kwargs.get('active_periods', None),
            meter_identifier=register_kwargs.get('meter_identifier', ""),
            quantity=register_kwargs.get('quantity', 0))
        r.utilbill = utility_bill
        session.add(r)
        session.flush()
        return r

    def update_register(self, register_id, rows):
        """Updates fields in the register given by 'register_id'
        """
        session = Session()

        #Register to be updated
        register = session.query(Register).filter(
            Register.id == register_id).one()

        for k in ['description', 'quantity', 'unit',
                  'identifier', 'estimated', 'reg_type', 'register_binding',
                  'meter_identifier']:
            val = rows.get(k, getattr(register, k))
            setattr(register, k, val)
        if 'active_periods' in rows and rows['active_periods'] is not None:
            active_periods_str = json.dumps(rows['active_periods'])
            register.active_periods = active_periods_str
        self.compute_utility_bill(register.utilbill_id)
        return register

    def delete_register(self, register_id):
        session = Session()
        register = session.query(Register).filter(
            Register.id == register_id).one()
        utilbill_id = register.utilbill_id
        utilbill = self._utilbill_loader.get_utilbill_by_id(utilbill_id)
        utilbill.check_editable()
        session.delete(register)
        session.commit()
        self.compute_utility_bill(utilbill_id)

    def add_charge(self, utilbill_id, **charge_kwargs):
        """Add a new charge to the given utility bill. charge_kwargs are
        passed as keyword arguments to the charge"""
        utilbill = self._utilbill_loader.get_utilbill_by_id(utilbill_id)
        utilbill.check_editable()
        charge = utilbill.add_charge(**charge_kwargs)
        self.compute_utility_bill(utilbill_id)
        return charge

    def update_charge(self, fields, charge_id=None, utilbill_id=None,
                      rsi_binding=None):
        """Modify the charge given by charge_id
        by setting key-value pairs to match the dictionary 'fields'."""
        assert charge_id or utilbill_id and rsi_binding
        session = Session()
        charge = session.query(Charge).filter(Charge.id == charge_id).one() \
            if charge_id else \
            session.query(Charge). \
                filter(Charge.utilbill_id == utilbill_id). \
                filter(Charge.rsi_binding == rsi_binding).one()
        utilbill = self._utilbill_loader.get_utilbill_by_id(charge.utilbill.id)
        utilbill.check_editable()
        for k, v in fields.iteritems():
            if k not in Charge.column_names():
                raise AttributeError("Charge has no attribute '%s'" % k)
            setattr(charge, k, v)
        session.flush()
        self.compute_utility_bill(charge.utilbill.id)
        return charge

    def delete_charge(self, charge_id):
        """Delete the charge given by 'charge_id' from its utility
        bill and recompute the utility bill. Raise ProcessedBillError if the
        utility bill is not editable.
        """
        session = Session()
        charge = session.query(Charge).filter_by(id=charge_id).one()
        charge.utilbill.check_editable()
        session.delete(charge)
        self.compute_utility_bill(charge.utilbill_id)
        session.expire(charge.utilbill)

    ############################################################################
    # CRUD methods for objects that are not children of UtilBill
    # TODO move somewhere else (or delete if unnecessary)
    ############################################################################

    def get_create_utility(self, name):
        session = Session()
        try:
            result = session.query(Utility).filter_by(name=name).one()
        except NoResultFound:
            result = Utility(name=name, address=Address())
            return result, True
        return result, False

    def get_create_supplier(self, name):
        session = Session()
        # suppliers are identified in the client by name, rather than
        # their primary key. "Unknown Supplier" is a name sent by the client
        # to the server to identify the supplier that is identified by "null"
        # when sent from the server to the client.
        if name == 'Unknown Supplier':
            return None
        try:
            result = session.query(Supplier).filter_by(name=name).one()
        except NoResultFound:
            result = Supplier(name=name, address=Address())
        return result

    def get_create_supply_group(self, name, supplier):
        session = Session()
        # supply_groups are identified in the client by name, rather than
        # their primary key. "Unknown Supply Group" is a name sent by the client
        # to the server to identify a supply group that is identified by "null"
        # when sent from the server to the client.
        if name == 'Unknown Supply Group':
            return None
        try:
            result = session.query(SupplyGroup).filter_by(name=name).one()
        except NoResultFound:
            result = SupplyGroup(name=name, supplier=supplier)
        return result

    def get_create_rate_class(self, rate_class_name, utility, service):
        assert isinstance(utility, Utility)
        session = Session()
        # rate classes are identified in the client by name, rather than
        # their primary key. "Unknown Rate Class" is a name sent by the client
        # to the server to identify the rate class that is identified by "null"
        # when sent from the server to the client.
        if rate_class_name == 'Unknown Rate Class':
            return None
        try:
            result = session.query(RateClass).filter_by(
                name=rate_class_name).one()
        except NoResultFound:
            result = RateClass(name=rate_class_name, utility=utility,
                               service=service)
        return result

    def update_utility_account_number(self, utility_account_id,
                                      utility_account_number):
        session = Session()
        try:
            utility_account = session.query(UtilityAccount).\
                filter(UtilityAccount.id==utility_account_id).one()
        except NoResultFound:
            raise
        utility_account.account_number = utility_account_number
        return utility_account



