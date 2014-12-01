import json
from datetime import datetime, timedelta

from billing.core.model import UtilBill, UtilBillLoader, Address, Charge, Register, Session, Supplier, Utility, \
    RateClass
from billing.exc import NoSuchBillException, DuplicateFileError


ACCOUNT_NAME_REGEX = '[0-9a-z]{5}'


class UtilbillProcessor(object):
    def __init__(self, rate_structure_dao, bill_file_handler, nexus_util,
                 logger=None):
        self.rate_structure_dao = rate_structure_dao
        self.bill_file_handler = bill_file_handler
        self.nexus_util = nexus_util
        self.logger = logger

    # TODO this method might be replaced by the UtilbillLoader method
    def _get_utilbill(self, utilbill_id):
        return UtilBillLoader(Session()).get_utilbill_by_id(utilbill_id)

    def get_utilbill_charges_json(self, utilbill_id):
        """Returns a list of dictionaries of charges for the utility bill given
        by  'utilbill_id' (MySQL id)."""
        session = Session()
        utilbill = session.query(UtilBill).filter_by(id=utilbill_id).one()
        return [charge.column_dict() for charge in utilbill.charges]

    def get_registers_json(self, utilbill_id):
        """Returns a dictionary of register information for the utility bill
        having the specified utilbill_id."""
        l = []
        session = Session()
        for r in session.query(Register).join(UtilBill,
            Register.utilbill_id == UtilBill.id).\
            filter(UtilBill.id == utilbill_id).all():
            l.append(r.column_dict())
        return l

    def new_register(self, utilbill_id, **register_kwargs):
        """Creates a new register for the utility bill having the specified id
        "row" argument is a dictionary but keys other than
        "meter_id" and "register_id" are ignored.
        """
        session = Session()
        utility_bill = session.query(UtilBill).filter_by(id=utilbill_id).one()
        if utility_bill.editable():
            r = Register(
                utility_bill,
                description=register_kwargs.get(
                    'description',"Insert description"),
                identifier=register_kwargs.get(
                    'identifier', "Insert register ID here"),
                unit=register_kwargs.get('unit', 'therms'),
                estimated=register_kwargs.get('estimated', False),
                reg_type=register_kwargs.get('reg_type', "total"),
                active_periods=register_kwargs.get('active_periods', None),
                meter_identifier=register_kwargs.get('meter_identifier', ""),
                quantity=register_kwargs.get('quantity', 0),
                register_binding=register_kwargs.get(
                    'register_binding', "Insert register binding here")
            )
            session.add(r)
            session.flush()
            return r

    def update_register(self, register_id, rows):
        """Updates fields in the register given by 'register_id'
        """
        self.logger.info("Running Process.update_register %s" % register_id)
        session = Session()

        #Register to be updated
        register = session.query(Register).filter(
            Register.id == register_id).one()

        for k in ['description', 'quantity', 'unit',
                  'identifier', 'estimated', 'reg_type', 'register_binding',
                  'meter_identifier']:
            val = rows.get(k, getattr(register, k))
            self.logger.debug("Setting attribute %s on register %s to %s" %
                              (k, register.id, val))
            setattr(register, k, val)
        if 'active_periods' in rows and rows['active_periods'] is not None:
            active_periods_str = json.dumps(rows['active_periods'])
            self.logger.debug("Setting attribute active_periods on register"
                              " %s to %s" % (register.id, active_periods_str))
            register.active_periods = active_periods_str
        self.logger.debug("Commiting changes to register %s" % register.id)
        self.compute_utility_bill(register.utilbill_id)
        return register

    def delete_register(self, register_id):
        self.logger.info("Running Process.delete_register %s" %
                         register_id)
        session = Session()
        register = session.query(Register).filter(
            Register.id == register_id).one()
        utilbill_id = register.utilbill_id
        utilbill = self._get_utilbill(utilbill_id)
        if utilbill.editable():
            session.delete(register)
            session.commit()
            self.compute_utility_bill(utilbill_id)

    def add_charge(self, utilbill_id, **charge_kwargs):
        """Add a new charge to the given utility bill. charge_kwargs are
        passed as keyword arguments to the charge"""
        utilbill = self._get_utilbill(utilbill_id)
        if utilbill.editable():
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
        utilbill = self._get_utilbill(charge.utilbill.id)
        if utilbill.editable():
            for k, v in fields.iteritems():
                if k not in Charge.column_names():
                    raise AttributeError("Charge has no attribute '%s'" % k)
                setattr(charge, k, v)
            session.flush()
            self.compute_utility_bill(charge.utilbill.id)
        return charge

    def delete_charge(self, charge_id=None, utilbill_id=None, rsi_binding=None):
        """Delete the charge given by 'rsi_binding' in the given utility
        bill."""
        assert charge_id or utilbill_id and rsi_binding
        utilbill = self._get_utilbill(utilbill_id)
        if utilbill.editable():
            session = Session()
            if charge_id:
                charge = session.query(Charge)\
                    .filter(Charge.id == charge_id).one()
            else:
                charge = session.query(Charge)\
                    .filter(Charge.utilbill_id == utilbill_id)\
                    .filter(Charge.rsi_binding == rsi_binding).one()
            session.delete(charge)
            self.compute_utility_bill(charge.utilbill_id)
            session.expire(charge.utilbill)

    def update_utilbill_metadata(
            self, utilbill_id, period_start=None, period_end=None, service=None,
            target_total=None, utility=None, supplier=None, rate_class=None,
            processed=None):
        """Update various fields for the utility bill having the specified
        `utilbill_id`. Fields that are not None get updated to new
        values while other fields are unaffected.
        """
        utilbill = self._get_utilbill(utilbill_id)
        #toggle processed state of utility bill
        if processed is not None:
                utilbill.processed = processed
        if utilbill.editable():
            if target_total is not None:
                utilbill.target_total = target_total

            if service is not None:
                utilbill.service = service

            if utility is not None and isinstance(utility, basestring):
                utilbill.utility = self.state_db.get_create_utility(utility)

            if supplier is not None and isinstance(supplier, basestring):
                utilbill.supplier = self.state_db.get_create_supplier(supplier)

            if rate_class is not None and isinstance(rate_class, basestring):
                utilbill.rate_class = self.state_db.get_create_rate_class(
                    rate_class, utilbill.utility)

            period_start = period_start if period_start else \
                utilbill.period_start
            period_end = period_end if period_end else utilbill.period_end

            UtilBill.validate_utilbill_period(period_start, period_end)
            utilbill.period_start = period_start
            utilbill.period_end = period_end
            self.compute_utility_bill(utilbill.id)
        return  utilbill

    def _create_utilbill_in_db(self, account, start=None, end=None,
                            service=None, utility=None, rate_class=None,
                            total=0, state=UtilBill.Complete, supplier=None):
        '''
        Returns a UtilBill with related objects (Charges and Registers
        assigned to it). Does not add anything to the session, so callers can
        do this only if no exception was raised by BillFileHandler when
        uploading the file.`
        :param account:
        :param start:
        :param end:
        :param service:
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
        customer = self.state_db.get_customer(account)
        try:
            predecessor = UtilBillLoader(session).get_last_real_utilbill(
                account, end=start, service=service)
            billing_address = predecessor.billing_address
            service_address = predecessor.service_address
        except NoSuchBillException as e:
            # If we don't have a predecessor utility bill (this is the first
            # utility bill we are creating for this customer) then we get the
            # closest one we can find by time difference, having the same rate
            # class and utility.

            q = session.query(UtilBill). \
                filter_by(rate_class=customer.fb_rate_class). \
                filter_by(utility=customer.fb_utility). \
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

            billing_address = customer.fb_billing_address
            service_address = customer.fb_service_address

        # order of preference for picking value of "service" field: value
        # passed as an argument, or 'electric' by default
        # TODO: this doesn't really make sense; probably the "service" field
        # should belong to the rate class.
        if service is None:
            service = getattr(predecessor, 'service', None)
        if service is None:
            service = 'electric'

        # order of preference for picking utility/supplier/rate_class: value
        # passed as an argument, same value as predecessor,
        # "fb" values from Customer
        # TODO: this is unnecessarily complicated.
        if utility is None:
            utility = getattr(predecessor, 'utility', None)
        if utility is None:
            utility = customer.fb_utility
        if supplier is None:
            supplier = getattr(predecessor, 'supplier', None)
        if supplier is None:
            supplier = customer.fb_supplier
        if rate_class is None:
            rate_class = getattr(predecessor, 'rate_class', None)
        if rate_class is None:
            rate_class = customer.fb_rate_class

        # delete any existing bill with same service and period but less-final
        # state
        customer = self.state_db.get_customer(account)
        new_utilbill = UtilBill(customer, state, service, utility, supplier,
                                rate_class, Address.from_other(billing_address),
                                Address.from_other(service_address),
                                period_start=start, period_end=end,
                                target_total=total,
                                date_received=datetime.utcnow().date())

        new_utilbill.charges = self.rate_structure_dao. \
            get_predicted_charges(new_utilbill)
        for register in predecessor.registers if predecessor else []:
            # no need to append this Register to new_utilbill.Registers because
            # SQLAlchemy does it automatically
            Register(new_utilbill, register.description, register.identifier,
                     register.unit, False, register.reg_type,
                     register.active_periods, register.meter_identifier,
                     quantity=0, register_binding=register.register_binding)
        return new_utilbill

    def upload_utility_bill(self, account, bill_file, start=None, end=None,
                            service=None, utility=None, rate_class=None,
                            total=0, state=UtilBill.Complete, supplier=None):
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
            utility = self.state_db.get_create_utility(utility)
        if rate_class is not None:
            rate_class = self.state_db.get_create_rate_class(rate_class, utility)
        if supplier is not None:
           supplier = self.state_db.get_create_supplier(supplier)
        new_utilbill = self._create_utilbill_in_db(
            account, start=start, end=end, service=service,utility=utility,
            rate_class=rate_class, total=total, state=state, supplier=supplier)

        # upload the file
        if bill_file is not None:
            self.bill_file_handler.upload_utilbill_pdf_to_s3(new_utilbill,
                                                             bill_file)

        # adding UtilBill should also add Charges and Registers due to cascade
        session = Session()
        session.add(new_utilbill)
        session.flush()

        self.compute_utility_bill(new_utilbill.id)

        return new_utilbill

    def upload_utility_bill_existing_file(self, account, utility_guid,
                                  sha256_hexdigest):
        '''Create a utility bill in the database corresponding to a file that
        has already been stored in S3.
        :param account: Nextility customer account number.
        :param utility_guid: specifies which utility this bill is for.
        :param sha256_hexdigest: SHA-256 hash of the existing file,
        which should also be (part of) the file name and sufficient to
        determine which existing file goes with this bill.
        '''
        s = Session()
        if UtilBillLoader(s).count_utilbills_with_hash(sha256_hexdigest) != 0:
            raise DuplicateFileError('Utility bill already exists with '
                                     'file hash %s' % sha256_hexdigest)

        # of all the UtilBill fields, only utility is known
        utility = s.query(Utility).filter_by(guid=utility_guid).one()
        new_utilbill = self._create_utilbill_in_db(account, utility=utility)

        # adding UtilBill should also add Charges and Registers due to cascade
        session = Session()
        session.add(new_utilbill)
        session.flush()

        self.compute_utility_bill(new_utilbill.id)

        # set hexdigest of the file (this would normally be done by
        # BillFileHandler.uppad_utilbill_pdf_to_s3)
        new_utilbill.sha256_hexdigest = sha256_hexdigest

        self.bill_file_handler.check_file_exists(new_utilbill)

        return new_utilbill

    def get_service_address(self, account):
        return UtilBillLoader(Session()).get_last_real_utilbill(
            account, end=datetime.utcnow()).service_address.to_dict()

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

        if utility_bill.is_attached() or not utility_bill.editable():
            raise ValueError("Can't delete an attached or processed utility bill.")

        self.bill_file_handler.delete_utilbill_pdf_from_s3(utility_bill)

        # TODO use cascade instead if possible
        for charge in utility_bill.charges:
            session.delete(charge)
        for register in utility_bill.registers:
            session.delete(register)
        session.delete(utility_bill)

        pdf_url = self.bill_file_handler.get_s3_url(utility_bill)
        return utility_bill, pdf_url

    def regenerate_uprs(self, utilbill_id):
        '''Resets the UPRS of this utility bill to match the predicted one.
        '''
        session = Session()
        utilbill = self._get_utilbill(utilbill_id)
        if utilbill.editable():
            for charge in utilbill.charges:
                session.delete(charge)
            utilbill.charges = []
            utilbill.charges = self.rate_structure_dao. \
                get_predicted_charges(utilbill)
        return self.compute_utility_bill(utilbill_id)

    def compute_utility_bill(self, utilbill_id):
        '''Updates all charges in the utility bill given by 'utilbill_id'.
        Also updates some keys in the document that are duplicates of columns
        in the MySQL table.
        '''
        utilbill = self._get_utilbill(utilbill_id)
        if utilbill.editable():
            utilbill.compute_charges()
        return utilbill

    def get_all_utilbills_json(self, account, start=None, limit=None):
        # result is a list of dictionaries of the form {account: account
        # number, name: full name, period_start: date, period_end: date,
        # sequence: reebill sequence number (if present)}
        utilbills, total_count = self.state_db.list_utilbills(account,
                                                              start, limit)
        data = [dict(ub.column_dict(),
                     pdf_url=self.bill_file_handler.get_s3_url(ub))
                for ub in utilbills]
        return data, total_count

    def get_all_suppliers_json(self):
        session = Session()
        return [s.column_dict() for s in session.query(Supplier).all()]

    def get_all_utilities_json(self):
        session = Session()
        return [u.column_dict() for u in session.query(Utility).all()]

    def get_all_rate_classes_json(self):
        session = Session()
        return [r.column_dict() for r in session.query(RateClass).all()]
