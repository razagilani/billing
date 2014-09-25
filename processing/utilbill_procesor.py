import json
from datetime import datetime, timedelta

from billing.processing.state import UtilBill, UtilBillLoader, Address, Charge, Register, Session
from billing.exc import NoSuchBillException


class UtilbillProcessor(object):
    def __init__(self, rate_structure_dao, billupload, nexus_util, journal_dao,
                 logger=None):
        self.rate_structure_dao = rate_structure_dao
        self.billupload = billupload
        self.nexus_util = nexus_util
        self.logger = logger
        self.journal_dao = journal_dao

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

    def new_register(self, utilbill_id, row):
        """Creates a new register for the utility bill having the specified id
        "row" argument is a dictionary but keys other than
        "meter_id" and "register_id" are ignored.
        """
        session = Session()
        utility_bill = session.query(UtilBill).filter_by(id=utilbill_id).one()
        r = Register(
            utility_bill,
            "Insert description",
            0,
            "therms",
            row.get('register_id', "Insert register ID here"),
            False,
            "total",
            "Insert register binding here",
            None,
            row.get('meter_id', ""))
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

        for k in ['description', 'quantity', 'quantity_units',
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
        session.delete(register)
        session.commit()
        self.compute_utility_bill(utilbill_id)

    def add_charge(self, utilbill_id):
        """Add a new charge to the given utility bill."""
        utilbill = self.state_db.get_utilbill_by_id(utilbill_id)
        charge = utilbill.add_charge()
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
        session = Session()
        charge = session.query(Charge).filter(Charge.id == charge_id).one() \
            if charge_id else \
            session.query(Charge). \
                filter(Charge.utilbill_id == utilbill_id). \
                filter(Charge.rsi_binding == rsi_binding).one()
        session.delete(charge)
        self.compute_utility_bill(charge.utilbill_id)
        session.expire(charge.utilbill)

    def update_utilbill_metadata(self, utilbill_id, period_start=None,
                                 period_end=None, service=None, target_total=None, utility=None,
                                 rate_class=None, processed=None):
        """Update various fields for the utility bill having the specified
        `utilbill_id`. Fields that are not None get updated to new
        values while other fields are unaffected.
        """
        utilbill = self.state_db.get_utilbill_by_id(utilbill_id)
        if target_total is not None:
            utilbill.target_total = target_total

        if service is not None:
            utilbill.service = service

        if utility is not None:
            utilbill.utility = utility

        if rate_class is not None:
            utilbill.rate_class = rate_class

        if processed is not None:
            utilbill.processed = processed

        period_start = period_start if period_start else utilbill.period_start
        period_end = period_end if period_end else utilbill.period_end

        UtilBill.validate_utilbill_period(period_start, period_end)
        utilbill.period_start = period_start
        utilbill.period_end = period_end

        self.compute_utility_bill(utilbill.id)
        return  utilbill

    def upload_utility_bill(self, account, service, begin_date,
                            end_date, bill_file, file_name, utility=None, rate_class=None,
                            total=0, state=UtilBill.Complete):
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
        # validate arguments
        if end_date <= begin_date:
            raise ValueError("Start date %s must precede end date %s" %
                             (begin_date, end_date))
        if end_date - begin_date > timedelta(days=365):
            raise ValueError(("Utility bill period %s to %s is longer than "
                              "1 year") % (begin_date, end_date))
        if bill_file is None and state in (UtilBill.UtilityEstimated,
                                           UtilBill.Complete):
            raise ValueError(("A file is required for a complete or "
                              "utility-estimated utility bill"))
        if bill_file is not None and state in (UtilBill.Hypothetical,
                                               UtilBill.Estimated):
            raise ValueError("Hypothetical or Estimated utility bills "
                             "can't have a file")

        session = Session()

        # find an existing utility bill that will provide rate class and
        # utility name for the new one, or get it from the template.
        # note that it doesn't matter if this is wrong because the user can
        # edit it after uploading.
        customer = self.state_db.get_customer(account)
        try:
            predecessor = UtilBillLoader(session).get_last_real_utilbill(
                account, begin_date, service=service)
            billing_address = predecessor.billing_address
            service_address = predecessor.service_address
        except NoSuchBillException as e:
            # If we don't have a predecessor utility bill (this is the first
            # utility bill we are creating for this customer) then we get the
            # closest one we can find by time difference, having the same rate
            # class and utility.

            q = session.query(UtilBill). \
                filter_by(rate_class=customer.fb_rate_class). \
                filter_by(utility=customer.fb_utility_name). \
                filter_by(processed=True). \
                filter(UtilBill.state != UtilBill.Hypothetical)

            next_ub = q.filter(UtilBill.period_start >= begin_date). \
                order_by(UtilBill.period_start).first()
            prev_ub = q.filter(UtilBill.period_start <= begin_date). \
                order_by(UtilBill.period_start.desc()).first()

            next_distance = (next_ub.period_start - begin_date).days if next_ub \
                else float('inf')
            prev_distance = (begin_date - prev_ub.period_start).days if prev_ub \
                else float('inf')

            predecessor = None if next_distance == prev_distance == float('inf') \
                else prev_ub if prev_distance < next_distance else next_ub

            billing_address = customer.fb_billing_address
            service_address = customer.fb_service_address

        utility = utility if utility else getattr(predecessor, 'utility', "")

        rate_class = rate_class if rate_class else \
            getattr(predecessor, 'rate_class', "")

        # delete any existing bill with same service and period but less-final
        # state
        customer = self.state_db.get_customer(account)
        new_utilbill = UtilBill(customer, state, service, utility, rate_class,
                                Address.from_other(billing_address),
                                Address.from_other(service_address),
                                period_start=begin_date, period_end=end_date,
                                target_total=total, date_received=datetime.utcnow().date())
        session.add(new_utilbill)
        session.flush()

        if bill_file is not None:
            # if there is a file, get the Python file object and name
            # string from CherryPy, and pass those to BillUpload to upload
            # the file (so BillUpload can stay independent of CherryPy)
            upload_result = self.billupload.upload(new_utilbill, account,
                                                   bill_file, file_name)
            if not upload_result:
                # TODO there is no test coverage for this situation; fix that
                # after utility bill files are stored in S3
                raise IOError('File upload failed: %s %s %s' % (
                    account, new_utilbill.id, file_name))
        session.flush()
        if state < UtilBill.Hypothetical:
            new_utilbill.charges = self.rate_structure_dao. \
                get_predicted_charges(new_utilbill, UtilBillLoader(session))
            for register in predecessor.registers if predecessor else []:
                session.add(Register(new_utilbill, register.description,
                                     0, register.quantity_units,
                                     register.identifier, False,
                                     register.reg_type,
                                     register.register_binding,
                                     register.active_periods,
                                     register.meter_identifier))
        session.flush()
        if new_utilbill.state < UtilBill.Hypothetical:
            self.compute_utility_bill(new_utilbill.id)
        return new_utilbill

    def get_service_address(self, account):
        return UtilBillLoader(Session()).get_last_real_utilbill(account,
                                                                datetime.utcnow()).service_address.to_dict()

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

        if utility_bill.is_attached():
            raise ValueError("Can't delete an attached utility bill.")

        try:
            path = self.billupload.delete_utilbill_file(utility_bill)
        except IOError:
            # file never existed or could not be found
            path = None

        # TODO use cascade instead if possible
        for charge in utility_bill.charges:
            session.delete(charge)
        for register in utility_bill.registers:
            session.delete(register)
        session.delete(utility_bill)

        return utility_bill, path

    def regenerate_uprs(self, utilbill_id):
        '''Resets the UPRS of this utility bill to match the predicted one.
        '''
        session = Session()
        utilbill = self.state_db.get_utilbill_by_id(utilbill_id)
        for charge in utilbill.charges:
            session.delete(charge)
        utilbill.charges = []
        utilbill.charges = self.rate_structure_dao. \
            get_predicted_charges(utilbill, UtilBillLoader(session))
        return self.compute_utility_bill(utilbill_id)

    def compute_utility_bill(self, utilbill_id):
        '''Updates all charges in the utility bill given by 'utilbill_id'.
        Also updates some keys in the document that are duplicates of columns
        in the MySQL table.
        '''
        utilbill = self.state_db.get_utilbill_by_id(utilbill_id)
        utilbill.compute_charges()
        return utilbill

    def get_all_utilbills_json(self, account, start=None, limit=None):
        # result is a list of dictionaries of the form {account: account
        # number, name: full name, period_start: date, period_end: date,
        # sequence: reebill sequence number (if present)}
        utilbills, total_count = self.state_db.list_utilbills(account,
                                                              start, limit)
        data = [ub.column_dict() for ub in utilbills]
        return data, total_count
