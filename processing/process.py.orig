#!/usr/bin/python
"""
File: process.py
Description: Various utility procedures to process bills
"""
import sys
import os
import copy
from datetime import date, datetime, timedelta
from operator import itemgetter
import traceback
from itertools import chain
from sqlalchemy.sql import desc, functions
from sqlalchemy import not_, and_
from sqlalchemy import func
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import aliased
from bson import ObjectId
#
# uuid collides with locals so both the locals and package are renamed
import re
import errno
import bson
from billing.processing import journal
from billing.processing.mongo import MongoReebill
from billing.processing import mongo
from billing.processing.rate_structure2 import RateStructure
from billing.processing import state
from billing.processing.state import Payment, Customer, UtilBill, ReeBill, \
    UtilBillLoader, ReeBillCharge, Address, Charge, Register, Reading
from billing.util.dateutils import estimate_month, month_offset, month_difference, date_to_datetime
from billing.util.monthmath import Month
from billing.util.dictutils import subdict
from billing.processing.exceptions import IssuedBillError, NotIssuable, \
    NoSuchBillException, NotUniqueException, \
    RSIError, NoSuchRSIError

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint
sys.stdout = sys.stderr

# number of days allowed between two non-Hypothetical utility bills before
# Hypothetical utility bills will be added between them.
# this was added to make the behavior of "hypothetical" utility bills less
# irritating, but really, they should never exist or at least never be stored
# in the database as if they were actual bills.
# see https://www.pivotaltracker.com/story/show/30083239
MAX_GAP_DAYS = 10

class Process(object):
    """ Class with a variety of utility procedures for processing bills.
        The idea here is that this class is instantiated with the data
        access objects it needs, and then ReeBills (why not just references
        to them?) are passed in and returned.  
    """

    config = None

    def __init__(self, state_db, reebill_dao, rate_structure_dao, billupload,
            nexus_util, bill_mailer, renderer, ree_getter,
            splinter=None, logger=None):
        '''If 'splinter' is not none, Skyline back-end should be used.'''
        self.state_db = state_db
        self.rate_structure_dao = rate_structure_dao
        self.reebill_dao = reebill_dao
        self.billupload = billupload
        self.nexus_util = nexus_util
        self.bill_mailer = bill_mailer
        self.ree_getter = ree_getter
        self.renderer = renderer
        self.splinter = splinter
        self.monguru = None if splinter is None else splinter.get_monguru()
        self.logger = logger
        self.journal_dao = journal.JournalDAO()

    def get_utilbill_doc(self, session, utilbill_id, reebill_sequence=None,
            reebill_version=None):
        '''Loads and returns the Mongo document for the utility bill given by
        'utilbill_id' (MySQL id). If the sequence and version of an issued
        reebill are given, the document returned will be the frozen version for
        the issued reebill.
        '''
        # NOTE this method is in Process because it uses both databases; is
        # there a better place to put it?

        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)

        if reebill_sequence is None:
            assert reebill_version is None
            # load editable utility bill document
            return self.reebill_dao.load_doc_for_utilbill(utilbill)

        # otherwise, load frozen utility bill document for the given reebill
        reebill = self.state_db.get_reebill(session, utilbill.customer.account,
                reebill_sequence, version=reebill_version)
        assert reebill.issued == True
        return self.reebill_dao.load_doc_for_utilbill(utilbill,
                reebill=reebill)

    def get_rs_doc(self, session, utilbill_id, rs_type, reebill_sequence=None,
            reebill_version=None):
        '''Loads and returns a rate structure document of type 'rs_type'
        ("uprs" only) for the utility bill given by 'utilbill_id' (MySQL
        id). If the sequence and version of an issued reebill are given, the
        document returned will be the frozen version for the issued reebill.
        '''
        # NOTE this method is in Process because it uses both databases; is
        # there a better place to put it?

        if rs_type == 'uprs':
            load_method = self.rate_structure_dao.load_uprs_for_utilbill
        else:
            raise ValueError(('Unknown "rs_type": expected "uprs", '
                    'got "%s"') % rs_type)

        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)

        if reebill_sequence is None:
            assert reebill_version is None
            # load editable utility bill document
            return load_method(utilbill)

        # otherwise, load frozen utility bill document for the given reebill
        reebill = self.state_db.get_reebill(session, utilbill.customer.account,
                reebill_sequence, version=reebill_version)
        assert reebill.issued == True
        return load_method(utilbill, reebill=reebill)

    def get_utilbill_charges_json(self, session, utilbill_id,
                    reebill_sequence=None, reebill_version=None):
        """Returns a list of dictionaries of charges for the utility bill given
        by  'utilbill_id' (MySQL id). If the sequence and version of an issued
        reebill are given, the document returned will be the frozen version for
        the issued reebill."""
        utilbill_doc = self.get_utilbill_doc(session, utilbill_id,
                reebill_sequence=reebill_sequence,
                reebill_version=reebill_version)
        utilbill = session.query(UtilBill).\
            filter_by(document_id=utilbill_doc['_id']).one()
        return [dict([(col, getattr(charge, col)) for col in
                     set(charge.column_names()) - set(['utilbill_id'])
                     if hasattr(charge, col)] + [('id', charge.rsi_binding)])
                for charge in utilbill.charges]

    def get_registers_json(self, session, utilbill_id):
        """Returns a dictionary of register information for the utility bill
        having the specified utilbill_id."""
        l = []
        for r in session.query(Register).join(UtilBill,
            Register.utilbill_id == UtilBill.id).\
            filter(UtilBill.id == utilbill_id).all():
            l.append(dict(meter_id=r.meter_identifier,
                          register_id=r.id,
                          service=r.utilbill.service,
                          type=r.reg_type,
                          binding=r.register_binding,
                          description=r.description,
                          quantity=r.quantity,
                          quantity_units=r.quantity_units,
                          id='%s/%s/%s' % (r.utilbill.service,
                                           r.meter_identifier,
                                           r.id)))
        return l

    def new_register(self, session, utilbill_id, row):
        """Creates a new register for the utility bill having the specified id"""
        utility_bill = session.query(UtilBill).filter_by(id=utilbill_id).one()
        session.add(Register(utility_bill,
                             "Insert description",
                             0,
                             "therms",
                             row.get('register_id', "Insert register ID here"),
                             False,
                             "total",
                             "Insert register binding here",
                             None,
                             row.get('meter_id', "")))
        session.commit()

    def update_register(self, session, utilbill_id, orig_meter_id, orig_reg_id,
                        rows):
        """Updates fields in the register given by 'original_register_id' in
        the meter given by 'original_meter_id', with the data contained by rows.
        """
        self.logger.info("Running Process.update_register %s %s %s" %
                         (utilbill_id, orig_meter_id, orig_reg_id))
        q = session.query(Register).join(UtilBill,
                                         Register.utilbill_id == UtilBill.id).\
            filter(UtilBill.id == utilbill_id)

        #Register to be updated
        register = q.filter(Register.meter_identifier == orig_meter_id).\
            filter(Register.identifier == orig_reg_id).one()

        #Check if a register with target register_id/meter_id already exists
        target_register_id = rows.get('register_id', orig_reg_id)
        target_meter_id = rows.get('meter_id', orig_meter_id)
        target = q.filter(Register.meter_identifier == target_meter_id).\
            filter(Register.identifier == target_register_id).first()
        if target and target != register:
            raise ValueError("There is already a register with id %s and meter"
                             " id %s" % (target_register_id, target_meter_id))

        for k in ['description', 'quantity', 'quantity_units',
                  'identifier', 'estimated', 'reg_type', 'register_binding',
                  'active_periods', 'meter_identifier']:
            val = rows.get(k, getattr(register, k))
            self.logger.debug("Setting attribute %s on register %s to %s" %
                              (k, register.id, val))
            setattr(register, k, val)
        self.logger.debug("Commiting changes to register %s" % register.id)
        session.commit()

    def delete_register(self, session, utilbill_id, orig_meter_id, orig_reg_id):
        self.logger.info("Running Process.delete_register %s %s %s" %
                         (utilbill_id, orig_meter_id, orig_reg_id))
        register = session.query(Register).join(UtilBill).\
            filter(UtilBill.id == utilbill_id).\
            filter(Register.meter_identifier == orig_meter_id).\
            filter(Register.identifier == orig_reg_id).one()
        session.delete(register)

    def add_charge(self, session, utilbill_id, group_name):
        """Add a new charge to the given utility bill with charge group
        "group_name" and default values for all its fields."""
        utilbill = session.query(UtilBill).filter_by(id=utilbill_id).one()
        utilbill.charges.append(Charge(utilbill, "", group_name, 0, "", 0, "", 0))

    def update_charge(self, session, utilbill_id, rsi_binding, fields):
        """Modify the charge given by 'rsi_binding' in the given utility
        bill by setting key-value pairs to match the dictionary 'fields'."""
        charge = session.query(Charge).join(UtilBill).\
            filter(UtilBill.id == utilbill_id).\
            filter(Charge.rsi_binding == rsi_binding).one()
        for k, v in fields.iteritems():
            setattr(charge, k, v)

    def delete_charge(self, session, utilbill_id, rsi_binding):
        """Delete the charge given by 'rsi_binding' in the given utility
        bill."""
        charge = session.query(Charge).join(UtilBill).\
            filter(UtilBill.id == utilbill_id).\
            filter(Charge.rsi_binding == rsi_binding).one()
        session.delete(charge)

    def get_rsis_json(self, session, utilbill_id):
        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)
        rs_doc = self.rate_structure_dao.load_uprs_for_utilbill(utilbill)
        return [rsi.to_dict() for rsi in rs_doc.rates]

    def add_rsi(self, session, utilbill_id):
        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)
        rs_doc = self.rate_structure_dao.load_uprs_for_utilbill(utilbill)
        new_rsi = rs_doc.add_rsi()
        rs_doc.save()
        return new_rsi

    def update_rsi(self, session, utilbill_id, rsi_binding, fields):
        '''Modify the charge given by 'rsi_binding' in the given utility
        bill by setting key-value pairs to match the dictionary 'fields'.
        '''
        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)
        rs_doc = self.rate_structure_dao.load_uprs_for_utilbill(utilbill)
        rsi = rs_doc.get_rsi(rsi_binding)
        rsi.update(**fields)
        rs_doc.save()
        return rsi.rsi_binding

    def delete_rsi(self, session, utilbill_id, rsi_binding):
        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)
        rs_doc = self.rate_structure_dao.load_uprs_for_utilbill(utilbill)
        rsi = rs_doc.get_rsi(rsi_binding)
        rs_doc.rates.remove(rsi)
        assert rsi not in rs_doc.rates
        rs_doc.save()

    def create_payment(self, session, account, date_applied, description,
            credit, date_received=None):
        '''Wrapper to create_payment method in state.py'''
        return self.state_db.create_payment(session, account, date_applied, description,
            credit, date_received)

    def update_payment(self, session, oid, date_applied, description, credit):
        '''Wrapper to update_payment method in state.py'''
        self.state_db.update_payment(session, oid, date_applied, description, credit)

    def delete_payment(self, session, oid):
        '''Wrapper to delete_payment method in state.py'''
        self.state_db.delete_payment(session, oid)

    def get_hypothetical_matched_charges(self, session, account, sequence):
        """Gets all hypothetical charges from a reebill for a service and
        matches the actual charge to each hypotheitical charge
        TODO: This method has no test coverage!"""
        reebill = self.state_db.get_reebill(session, account, sequence)
        charge_map = {c.rsi_binding : c for c in reebill.utilbill.charges}
        result = []
        for hypothetical_charge in reebill.charges:
            try:
                matching = charge_map[hypothetical_charge.rsi_binding]
            except KeyError:
                raise NoSuchRSIError('The set of charges on the Reebill do not'
                                     ' match the charges on the associated'
                                     ' utility bill. Please recompute the'
                                     ' ReeBill.')
            result.append({
                'rsi_binding': matching.rsi_binding,
                'description': matching.description,
                'actual_quantity': matching.quantity,
                'actual_rate': matching.rate,
                'actual_total': matching.total,
                'quantity_units': matching.quantity_units,
                'hypothetical_quantity': hypothetical_charge.h_quantity,
                'hypothetical_rate': hypothetical_charge.h_rate,
                'hypothetical_total': hypothetical_charge.h_total
            })
        return result

    def update_utilbill_metadata(self, session, utilbill_id, period_start=None,
            period_end=None, service=None, total_charges=None, utility=None,
            rate_class=None, processed=None):
        '''Update various fields in MySQL and Mongo for the utility bill whose
        MySQL id is 'utilbill_id'. Fields that are not None get updated to new
        values while other fields are unaffected.
        '''
        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)

        # save period dates for use in moving the utility bill file at the end
        # of this method
        old_start, old_end = utilbill.period_start, utilbill.period_end

        # load Mongo document

        # 'load_doc_for_utilbill' should load an editable document always, not
        # one attached to a reebill
        doc = self.reebill_dao.load_doc_for_utilbill(utilbill)
        assert 'sequence' not in doc
        assert 'version' not in doc

        # for total charges, it doesn't matter whether a reebill exists
        if total_charges is not None:
            utilbill.total_charges = total_charges

        # for service and period dates, a reebill must be updated if it does
        # exist

        if service is not None:
            doc['service'] = service
            utilbill.service = service

        if utility is not None:
            utilbill.utility = utility
            doc['utility'] = utility

        if rate_class is not None:
            utilbill.rate_class = rate_class
            doc['rate_class'] = rate_class
            
        if processed is not None:
            utilbill.processed=processed

        if period_start is not None:
            UtilBill.validate_utilbill_period(period_start, utilbill.period_end)
            utilbill.period_start = period_start
            doc['start'] = period_start
            for meter in doc['meters']:
                meter['prior_read_date'] = period_start

        if period_end is not None:
            UtilBill.validate_utilbill_period(utilbill.period_start, period_end)
            utilbill.period_end = period_end
            doc['end'] = period_end
            for meter in doc['meters']:
                meter['present_read_date'] = period_end

        # delete any Hypothetical utility bills that were created to cover gaps
        # that no longer exist
        self.state_db.trim_hypothetical_utilbills(session,
                utilbill.customer.account, utilbill.service)

        # save in Mongo last because it can't be rolled back
        self.reebill_dao.save_utilbill(doc)


    def get_reebill_metadata_json(self, session, account):
        '''Returns data from both MySQL and Mongo describing all reebills for
        the given account, as list of JSON-ready dictionaries.
        '''
        result = []

        # this subquery gets (customer_id, sequence, version) for all the
        # reebills whose version is the maximum in their (customer, sequence,
        # version) group.
        latest_versions_sq = session.query(ReeBill.customer_id,
                ReeBill.sequence,
                functions.max(ReeBill.version).label('max_version'))\
                .join(Customer)\
                .filter(Customer.account==account)\
                .order_by(ReeBill.customer_id, ReeBill.sequence).group_by(
                ReeBill.customer, ReeBill.sequence).subquery()

        # query ReeBill joined to the above subquery to get only
        # maximum-version bills, and also outer join to ReeBillCharge to get
        # sum of 0 or more charges associated with each reebill
        q = session.query(ReeBill,
                # NOTE functions.sum(Reading.renewable_quantity) can't be used
                # here to get total energy, because of unit conversion. instead
                # the method ReeBill.get_total_renewable_energy must be used to
                # calculate it.
                functions.sum(ReeBillCharge.h_total).label('total_charge')
                ).join(latest_versions_sq, and_(
                ReeBill.customer_id == latest_versions_sq.c.customer_id,
                ReeBill.sequence == latest_versions_sq.c.sequence,
                ReeBill.version == latest_versions_sq.c.max_version)
        ).outerjoin(ReeBillCharge)\
        .order_by(desc(ReeBill.sequence)).group_by(ReeBill.id)

        for reebill, total_charge in q:
            # load utility bill document for this reebill:
            # use "frozen" document's id in utilbill_reebill table if present,
            # otherwise "current" id in utility bill table
            # TODO loading utility bill document from Mongo should be
            # unnecessary when "actual" versions of each reebill charge are
            # moved to MySQL
            frozen_doc_id = reebill._utilbill_reebills[0].document_id
            current_doc_id = reebill.utilbills[0].document_id
            if frozen_doc_id is None:
                utilbill_doc = self.reebill_dao._load_utilbill_by_id(current_doc_id)
            else:
                utilbill_doc = self.reebill_dao._load_utilbill_by_id(frozen_doc_id)

            the_dict = {
                'id': reebill.sequence,
                'sequence': reebill.sequence,
                'issue_date': reebill.issue_date,
                'period_start': reebill.utilbills[0].period_start,
                'period_end': reebill.utilbills[0].period_end,
                'max_version': reebill.version,
                'issued': bool(reebill.issued),
                # NOTE SQL sum() over no rows returns NULL, must substitute 0
                'hypothetical_total': total_charge or 0,
                'actual_total': mongo.total_of_all_charges(utilbill_doc),
                'ree_value': reebill.ree_value,
                'ree_charges': reebill.ree_charge,
                # invisible columns
                'prior_balance': reebill.prior_balance,
                'total_error': self.get_total_error(session, account,
                                                    reebill.sequence),
                'balance_due': reebill.balance_due,
                'payment_received': reebill.payment_received,
                'total_adjustment': reebill.total_adjustment,
                'balance_forward': reebill.balance_forward,
                # TODO: is this used at all? does it need to be populated?
                'services': [],
            }
            if reebill.version > 0:
                if reebill.issued:
                    the_dict['corrections'] = str(reebill.version)
                else:
                    the_dict['corrections'] = '#%s not issued' % reebill.version
            else:
                the_dict['corrections'] = '-' if reebill.issued else '(never ' \
                                                                     'issued)'

            # wrong energy unit can make this method fail causing the reebill
            # grid to not load; see
            # https://www.pivotaltracker.com/story/show/59594888
            try:
                the_dict['ree_quantity'] = reebill.get_total_renewable_energy()
            except (ValueError, StopIteration) as e:
                self.logger.error("Error when getting renewable energy "
                        "quantity for reebill %s-%s-%s:\n%s" % (
                        account, reebill.sequence, reebill.version,
                        traceback.format_exc()))
                the_dict['ree_quantity'] = 'ERROR: %s' % e.message

            result.append(the_dict)
        return result

    def get_sequential_account_info(self, session, account, sequence):
        reebill = self.state_db.get_reebill(session, account, sequence)
        return {
            'billing_address': reebill.billing_address.to_dict(),
            'service_address': reebill.service_address.to_dict(),
            'discount_rate': reebill.discount_rate,
            'late_charge_rate': reebill.late_charge_rate,
        }

    def update_sequential_account_info(self, session, account, sequence,
            discount_rate=None, late_charge_rate=None,
            ba_addressee=None, ba_street=None, ba_city=None, ba_state=None,
            ba_postal_code=None,
            sa_addressee=None, sa_street=None, sa_city=None, sa_state=None,
            sa_postal_code=None):
        '''Update fields for the reebill given by account, sequence
        corresponding to the "sequential account information" form in the UI,
        '''
        reebill = self.state_db.get_reebill(session, account, sequence)
        if reebill.issued:
            raise IssuedBillError("Can't modify an issued reebill")

        if discount_rate is not None:
            reebill.discount_rate = discount_rate
        if late_charge_rate is not None:
            reebill.late_charge_rate = late_charge_rate

        if ba_addressee is not None:
            reebill.billing_address.addressee = ba_addressee
        if ba_street is not None:
            reebill.billing_address.street = ba_street
        if ba_street is not None:
            reebill.billing_address.street = ba_street
        if ba_city is not None:
            reebill.billing_address.city = ba_city
        if ba_postal_code is not None:
            reebill.billing_address.postal_code = ba_postal_code

        if sa_addressee is not None:
            reebill.service_address.addressee = sa_addressee
        if sa_street is not None:
            reebill.service_address.street = sa_street
        if sa_street is not None:
            reebill.service_address.street = sa_street
        if sa_city is not None:
            reebill.service_address.city = sa_city
        if sa_postal_code is not None:
            reebill.service_address.postal_code = sa_postal_code

    def upload_utility_bill(self, session, account, service, begin_date,
            end_date, bill_file, file_name, utility=None, rate_class=None,
            total=0, state=UtilBill.Complete):
        '''Uploads 'bill_file' with the name 'file_name' as a utility bill for
        the given account, service, and dates. If the upload succeeds, a row is
        added to the utilbill table in MySQL and a document is added in Mongo
        (based on a previous bill or the template). If this is the newest or
        oldest utility bill for the given account and service, "estimated"
        utility bills will be added to cover the gap between this bill's period
        and the previous newest or oldest one respectively. The total of all
        charges on the utility bill may be given.

        Returns the newly created UtilBill object.
        
        Currently 'utility' and 'rate_class' are ignored in favor of the
        predecessor's (or template's) values; see
        https://www.pivotaltracker.com/story/show/52495771
        '''
        # validate arguments
        if end_date <= begin_date:
            raise ValueError("Start date %s must precede end date %s" %
                    (begin_date, end_date))
        if end_date - begin_date > timedelta(days=365):
            raise ValueError(("Utility bill period %s to %s is longer than "
                "1 year") % (begin_date, begin_date))
        if bill_file is None and state in (UtilBill.UtilityEstimated,
                UtilBill.Complete):
            raise ValueError(("A file is required for a complete or "
                    "utility-estimated utility bill"))
        if bill_file is not None and state in (UtilBill.Hypothetical,
                UtilBill.SkylineEstimated):
            raise ValueError("Hypothetical or Skyline-estimated utility bills "
                    "can't have file")

        # NOTE 'total' does not yet go into the utility bill document in Mongo

        # get & save end date of last bill (before uploading a new bill which
        # may come later)
        original_last_end = self.state_db.last_utilbill_end_date(session,
                account)

        # find an existing utility bill that will provide rate class and
        # utility name for the new one, or get it from the template.
        # note that it doesn't matter if this is wrong because the user can
        # edit it after uploading.
        customer = self.state_db.get_customer(session, account)
        try:
            predecessor = self.state_db.get_last_real_utilbill(session, account,
                             begin_date, service=service)
            billing_address = predecessor.billing_address
            service_address = predecessor.service_address
        except NoSuchBillException as e:
            # If we don't have a predecessor utility bill (this is the first
            # utility bill we are creating for this customer) then we get the
            # closest one we can find by time difference, having the same rate
            # class and utility.

            q = session.query(UtilBill).\
                filter_by(rate_class=customer.fb_rate_class).\
                filter_by(utility=customer.fb_utility_name).\
                filter_by(processed=True).\
                filter(UtilBill.state != UtilBill.Hypothetical)

            next_ub = q.filter(UtilBill.period_start >= begin_date).\
                order_by(UtilBill.period_start).first()
            prev_ub = q.filter(UtilBill.period_start <= begin_date).\
                order_by(UtilBill.period_start.desc()).first()

            next_distance = (next_ub.period_start - begin_date).days if next_ub\
                else float('inf')
            prev_distance = (begin_date - prev_ub.period_start).days if prev_ub\
                else float('inf')

            predecessor = None if next_distance == prev_distance == float('inf')\
                else prev_ub if prev_distance < next_distance else next_ub

            billing_address = customer.fb_billing_address
            service_address = customer.fb_service_address

        utility = utility if utility else getattr(predecessor, 'utility', "")

        rate_class = rate_class if rate_class else \
            getattr(predecessor, 'rate_class', "")

        # delete any existing bill with same service and period but less-final
        # state
        customer = self.state_db.get_customer(session, account)
        bill_to_replace = self._find_replaceable_utility_bill(session,
                customer, service, begin_date, end_date, state)
        if bill_to_replace is not None:
            session.delete(bill_to_replace)

        # create new UtilBill document (it does not have any mongo document
        # _ids yet but these are created below)
        # NOTE SQLAlchemy automatically adds this UtilBill to the session, so
        # calling session.add() is superfluous; see
        # https://www.pivotaltracker.com/story/show/26147819
        new_utilbill = UtilBill(customer, state, service, utility, rate_class,
                Address.from_other(billing_address),
                Address.from_other(service_address),
                period_start=begin_date, period_end=end_date,
                total_charges=total, date_received=datetime.utcnow().date())
        session.add(new_utilbill)
        session.flush()

        if bill_file is not None:
            # if there is a file, get the Python file object and name
            # string from CherryPy, and pass those to BillUpload to upload
            # the file (so BillUpload can stay independent of CherryPy)
            upload_result = self.billupload.upload(new_utilbill, account,
                                                   bill_file, file_name)
            if not upload_result:
                raise IOError('File upload failed: %s %s %s' % (account,
                    new_utilbill.id, file_name))

        # save 'new_utilbill' in MySQL with _ids from Mongo docs, and save the
        # 3 mongo docs in Mongo (unless it's a 'Hypothetical' utility bill,
        # which has no documents)

        if state < UtilBill.Hypothetical:
            doc, uprs = self._generate_docs_for_new_utility_bill(session,
                new_utilbill, predecessor)
            new_utilbill.document_id = str(doc['_id'])
            new_utilbill.uprs_document_id = str(uprs.id)
            self.reebill_dao.save_utilbill(doc)
            uprs.save()

            if predecessor is not None:

                valid_bindings = set([rsi['rsi_binding'] for rsi in uprs.rates])
                for charge in predecessor.charges:
                    if charge.rsi_binding not in valid_bindings:
                        continue
                    new_utilbill.charges.append(Charge(new_utilbill,
                                                       charge.description,
                                                       charge.group,
                                                       charge.quantity,
                                                       charge.quantity_units,
                                                       charge.rate,
                                                       charge.rsi_binding,
                                                       charge.total))
                for register in predecessor.registers:
                    session.add(Register(new_utilbill, register.description,
                                         0, register.quantity_units,
                                         register.identifier, False,
                                         register.reg_type,
                                         register.register_binding,
                                         register.active_periods,
                                         register.meter_identifier))

        # if begin_date does not match end date of latest existing bill, create
        # hypothetical bills to cover the gap
        # NOTE hypothetical bills are not created if the gap is small enough
        if original_last_end is not None and begin_date > original_last_end \
                and begin_date - original_last_end > \
                timedelta(days=MAX_GAP_DAYS):
            self.state_db.fill_in_hypothetical_utilbills(session, account,
                    service, utility, rate_class, original_last_end,
                    begin_date)
        return new_utilbill

    def get_service_address(self,session,account):
        '''Finds the last state.Utilbill, loads the mongo document for it,
        and extracts the service address from it '''
        utilbill=self.state_db.get_last_real_utilbill(session, account,
                                                      datetime.now())
        utilbill_doc=self.reebill_dao.load_doc_for_utilbill(utilbill)
        address=mongo.get_service_address(utilbill_doc)
        return address

    def _find_replaceable_utility_bill(self, session, customer, service, start,
            end, state):
        '''Returns exactly one state.UtilBill that should be replaced by
        'new_utilbill' which is about to be uploaded (i.e. has the same
        customer, period, and service, but a less-final state). Returns None if
        there is no such bill. A NotUniqueException is raised if more than one
        utility bill matching these criteria is found.
        
        Note: customer, service, start, end are passed in instead of a new
        UtilBill because SQLAlchemy automatically adds any UtilBill that is
        instantiated to the session, which breaks the test for matching utility
        bills that already exist.'''
        # TODO 38385969: is this really a good idea?

        # get existing bills matching dates and service
        # (there should be at most one, but you never know)
        existing_bills = session.query(UtilBill)\
                .filter_by(customer=customer)\
                .filter_by(service=service)\
                .filter_by(period_start=start)\
                .filter_by(period_end=end)
        try:
            existing_bill = existing_bills.one()
        except NoResultFound:
            return None
        except MultipleResultsFound:
            raise NotUniqueException(("Can't upload a bill for dates %s, %s "
                    "because there are already %s of them") % (start,
                    end, len(list(existing_bills))))

        # now there is one existing bill with the same dates. if state is
        # "more final" than an existing non-final bill that matches this
        # one, that bill should be replaced with the new one
        # (states can be compared with '<=' because they're ordered from
        # "most final" to least--see state.UtilBill)
        if existing_bill.state <= state:
            # TODO this error message is kind of obscure
            raise NotUniqueException(("Can't upload a utility bill for "
                "dates %s, %s because one already exists with a more final"
                " state than %s") % (start, end, state))

        return existing_bill


    def _generate_docs_for_new_utility_bill(self, session, utilbill,
                                            predecessor):
        '''Returns utility bill doc, UPRS doc for the given
        StateDB.UtilBill which is about to be added to the database, using the
        last utility bill with the same account, service, and rate class, or
        the account's template if no such bill exists. 'utilbill' must be at
        most 'SkylineEstimated', 'Hypothetical' because 'Hypothetical' utility
        bills have no documents. No database changes are made.'''
        assert utilbill.state < UtilBill.Hypothetical

        if predecessor is None:
            doc = {
                '_id': ObjectId(),
                'charges': [],
                'meters': []
            }
        else:
            # the preceding utility bill does exist, so get its UPRS
            doc = self.reebill_dao.load_doc_for_utilbill(predecessor)
            # NOTE this is a temporary workaround for a bug in MongoEngine
            # 0.8.4 described here:
            # https://www.pivotaltracker.com/story/show/57593308
            predecessor_uprs = self.rate_structure_dao.load_uprs_for_utilbill(
                    predecessor)
            predecessor_uprs.validate()
            doc.update({
                '_id': ObjectId(),
                'start': date_to_datetime(utilbill.period_start),
                'end': date_to_datetime(utilbill.period_end),
                 # update the document's "account" field just in case it's wrong or
                 # two accounts are sharing the same template document
                'account': utilbill.customer.account,
            })

        # generate predicted UPRS
        uprs = self.rate_structure_dao.get_predicted_rate_structure(utilbill,
                UtilBillLoader(session))
        uprs.id = ObjectId()

        # remove charges that don't correspond to any RSI binding (because
        # their corresponding RSIs were not part of the predicted rate structure)
        valid_bindings = {rsi['rsi_binding']: False for rsi in uprs.rates}
        i = 0
        while i < len(doc['charges']):
            charge = doc['charges'][i]
            # if the charge matches a valid RSI binding, mark that
            # binding as matched; if not, delete the charge
            if charge['rsi_binding'] in valid_bindings:
                valid_bindings[charge['rsi_binding']] = True
                i += 1
            else:
                doc['charges'].pop(i)

        # TODO add a charge for every RSI that doesn't have a charge, i.e.
        # the ones whose value in 'valid_bindings' is False.
        # we can't do this yet because we don't know what group it goes in.
        # see https://www.pivotaltracker.com/story/show/43797365

        return doc, uprs


    def delete_utility_bill_by_id(self, session, utilbill_id):
        '''Deletes the utility bill given by its MySQL id 'utilbill_id' (if
        it's not attached to a reebill) and returns the deleted state
        .UtilBill object and the path  where the file was moved (it never
        really gets deleted). This path will be None if there was no file or
        it could not be found. Raises a ValueError if the
        utility bill cannot be deleted.
        '''
        # load utilbill to get its dates and service
        utilbill = session.query(state.UtilBill) \
                .filter(state.UtilBill.id == utilbill_id).one()
        # delete it & get new path (will be None if there was never
        # a utility bill file or the file could not be found)
        _, deleted_path = self.delete_utility_bill(session,
                utilbill)
        return utilbill, deleted_path

    # TODO merge with delete_utility_bill_by_id
    def delete_utility_bill(self, session, utilbill):
        '''Deletes the utility bill given by its MySQL id 'utilbill_id' (if
        it's not attached to a reebill) and returns the path where the file was
        moved (it never really gets deleted). This path will be None if there
        was no file or it could not be found. Raises a ValueError if the
        utility bill cannot be deleted.'''
        if utilbill.is_attached():
            raise ValueError("Can't delete an attached utility bill.")

        # OK to delete now.
        # first try to delete the file on disk
        try:
            new_path = self.billupload.delete_utilbill_file(utilbill)
        except IOError:
            # file never existed or could not be found
            new_path = None

        # delete from MySQL
        # TODO move to StateDB?
        session.delete(utilbill)

        self.state_db.trim_hypothetical_utilbills(session,
                utilbill.customer.account, utilbill.service)

        # delete utility bill, UPRS documents from Mongo (which should
        # exist iff the utility bill is not "Hypothetical")
        if utilbill.state < UtilBill.Hypothetical:
            self.reebill_dao.delete_doc_for_statedb_utilbill(utilbill)
            self.rate_structure_dao.delete_rs_docs_for_utilbill(utilbill)
        else:
            assert utilbill.state == UtilBill.Hypothetical
            assert utilbill.document_id is None
            assert utilbill.uprs_document_id is None


        # delete any estimated utility bills that were created to
        # cover gaps that no longer exist
        self.state_db.trim_hypothetical_utilbills(session,
            utilbill.customer.account, utilbill.service)

        return utilbill, new_path

    def regenerate_uprs(self, session, utilbill_id):
        '''Resets the UPRS of this utility bill to match the predicted one.
        '''
        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)
        existing_uprs = self.rate_structure_dao.load_uprs_for_utilbill(
                utilbill)
        new_rs = self.rate_structure_dao.get_predicted_rate_structure(utilbill,
                UtilBillLoader(session))
        existing_uprs.rates = new_rs.rates
        existing_uprs.save()

    def has_utilbill_predecessor(self, session, utilbill_id):
        try:
            utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)
            predecessor = self.state_db.get_last_real_utilbill(session,
                    utilbill.customer.account, utilbill.period_start,
                    utility=utilbill.utility, service=utilbill.service)
            return True
        except NoSuchBillException:
            return False

    def refresh_charges(self, session, utilbill_id):
        '''Replaces charges in the utility bill document with newly-created
        ones based on its rate structures. A charge is created for every Rate
        Structure Item in the UPRS. The charges are computed according to the
        rate structure.
        '''
        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)
        document = self.reebill_dao.load_doc_for_utilbill(utilbill)
        uprs = self.rate_structure_dao.load_uprs_for_utilbill(utilbill)
        utilbill.refresh_charges(uprs.rates)
        try:
            utilbill.compute_charges(uprs, document) #document for meter info
        except Exception as e:
            session.commit()
            raise

    def compute_utility_bill(self, session, utilbill_id):
        '''Updates all charges in the document of the utility bill given by
        'utilbill_id' so they are correct according to its rate structure, and
        saves the document.
        '''
        utilbill = self.state_db.get_utilbill_by_id(session, utilbill_id)
        document = self.reebill_dao.load_doc_for_utilbill(utilbill)

        # update Mongo document to match "metadata" columns in MySQL:
        document.update({
            'account': utilbill.customer.account,
            'start': utilbill.period_start,
            'end': utilbill.period_end,
            'service': utilbill.service,
            'utility': utilbill.utility,
            'rate_class': utilbill.rate_class,
        })

        uprs = self.rate_structure_dao.load_uprs_for_utilbill(utilbill)

        mongo.compute_all_charges(document, uprs)

        # also try to compute documents of any unissued reebills associated
        # with this utility bill
        for reebill in (ur.reebill for ur in utilbill._utilbill_reebills if not
                ur.reebill.issued):
            try:
                self.compute_reebill(session, reebill.customer.account,
                    reebill.sequence, version=reebill.version)
            except Exception as e:
                self.logger.error("Error when computing reebill %s: %s" % (
                        reebill, e))

        self.reebill_dao.save_utilbill(document)

    def compute_reebill(self, session, account, sequence, version='max'):
        '''Loads, computes, and saves the reebill from MySQL and the reebill
        document in Mongo.
        '''
        reebill = self.state_db.get_reebill(session, account, sequence,
                version)

        reebill.copy_reading_conventional_quantities_from_utility_bill()
        uprs = self.rate_structure_dao.load_uprs_for_utilbill(reebill.utilbill)
        reebill.compute_charges(uprs, self.reebill_dao)

        actual_total = reebill.utilbill.total_charge()
        hypothetical_total = reebill.get_total_hypothetical_charges()
        reebill.ree_value = hypothetical_total - actual_total
        reebill.ree_charge = reebill.ree_value * (1 - reebill.discount_rate)
        reebill.ree_savings = reebill.ree_value * reebill.discount_rate

        # compute adjustment: this bill only gets an adjustment if it's the
        # earliest unissued version-0 bill, i.e. it meets 2 criteria:
        # (1) it's a version-0 bill, not a correction
        # (2) at least the 0th version of its predecessor has been issued (it
        #     may have an unissued correction; if so, that correction will
        #     contribute to the adjustment on this bill)
        if reebill.sequence == 1:
            reebill.total_adjustment = 0

            # include all payments since the beginning of time, in case there
            # happen to be any.
            # if any version of this bill has been issued, get payments up
            # until the issue date; otherwise get payments up until the
            # present.
            present_v0_issue_date = self.state_db.get_reebill(session,
                  account, sequence, version=0).issue_date
            if present_v0_issue_date is None:
                reebill.payment_received = self.state_db. \
                    get_total_payment_since(session, account,
                                            state.MYSQLDB_DATETIME_MIN)
            else:
                reebill.payment_received = self.state_db. \
                    get_total_payment_since(session, account,
                                            state.MYSQLDB_DATETIME_MIN,
                                            end=present_v0_issue_date)
            # obviously balances are 0
            reebill.prior_balance = 0
            reebill.balance_forward = 0

            # NOTE 'calculate_statistics' is not called because statistics
            # section should already be zeroed out
        else:
            predecessor = self.state_db.get_reebill(session, account,
                    reebill.sequence - 1, version=0)
            if reebill.version == 0 and predecessor.issued:
                reebill.total_adjustment = self.get_total_adjustment(session,
                                                                     account)

            # get payment_received: all payments between issue date of
            # predecessor's version 0 and issue date of current reebill's version 0
            # (if current reebill is unissued, its version 0 has None as its
            # issue_date, meaning the payment period lasts up until the present)
            if predecessor.issued:
                # if predecessor's version 0 is issued, gather all payments from
                # its issue date until version 0 issue date of current bill, or
                # today if this bill has never been issued
                if self.state_db.is_issued(session, account,
                                reebill.sequence, version=0):
                    present_v0_issue_date = self.state_db.get_reebill(session,
                            account, reebill.sequence,
                            version=0).issue_date
                    reebill.payment_received = self.state_db. \
                            get_total_payment_since(session, account,
                            predecessor.issue_date,
                            end=present_v0_issue_date)
                else:
                    reebill.payment_received = self.state_db. \
                            get_total_payment_since(session, account,
                            predecessor.issue_date)
            else:
                # if predecessor is not issued, there's no way to tell what
                # payments will go in this bill instead of a previous bill, so
                # assume there are none (all payments since last issue date go in
                # the account's first unissued bill)
                reebill.payment_received = 0

            reebill.prior_balance = predecessor.balance_due
            reebill.balance_forward = predecessor.balance_due - \
                  reebill.payment_received + reebill.total_adjustment

        # include manually applied adjustment
        reebill.balance_forward += reebill.manual_adjustment

        # set late charge, if any (this will be None if the previous bill has
        # not been issued, 0 before the previous bill's due date, and non-0
        # after that)
        lc = self.get_late_charge(session, reebill)
        reebill.late_charge = lc or 0
        reebill.balance_due = reebill.balance_forward + reebill.ree_charge + \
                reebill.late_charge

    def roll_reebill(self, session, account, integrate_skyline_backend=True,
                     start_date=None, skip_compute=False):
        """ Create first or roll the next reebill for given account.
        After the bill is rolled, this function also binds renewable energy data
        and computes the bill by default. This behavior can be modified by
        adjusting the appropriate parameters.
        'start_date': must be given for the first reebill.
        'integrate_skyline_backend': this must be True to get renewable energy
                                     data.
        'skip_compute': for tests that want to check for correct default
                        values before the bill was computed"""
        # 1st transaction: roll
        customer = self.state_db.get_customer(session, account)
        last_reebill_row = session.query(ReeBill)\
                .filter(ReeBill.customer == customer)\
                .order_by(desc(ReeBill.sequence), desc(ReeBill.version)).first()

        new_utilbills, new_utilbill_docs = [], []
        if last_reebill_row is None:
            # No Reebills are associated with this account: Create the first one
            assert start_date is not None
            utilbill = session.query(UtilBill)\
                    .filter(UtilBill.customer == customer)\
                    .filter(UtilBill.period_start >= start_date)\
                    .order_by(UtilBill.period_start).first()
            if utilbill is None:
                raise ValueError("No utility bill found starting on/after %s" %
                        start_date)
            new_utilbills.append(utilbill)
            new_utilbill_docs.append(
                        self.reebill_dao.load_doc_for_utilbill(utilbill))

            new_sequence = 1
        else:
            # There are Reebills associated with this account: Create the next Reebill
            # First, find the successor to every utility bill belonging to the reebill, along
            # with its mongo document. note that Hypothetical utility bills are
            # excluded.
            for utilbill in last_reebill_row.utilbills:
                successor = session.query(UtilBill)\
                    .filter(UtilBill.customer == customer)\
                    .filter(not_(UtilBill._utilbill_reebills.any()))\
                    .filter(UtilBill.service == utilbill.service)\
                    .filter(UtilBill.utility == utilbill.utility)\
                    .filter(UtilBill.period_start >= utilbill.period_end)\
                    .order_by(UtilBill.period_end).first()
                if successor is None:
                    raise NoSuchBillException(("Couldn't find next "
                            "utility bill following %s") % utilbill)
                if successor.state == UtilBill.Hypothetical:
                    raise NoSuchBillException(('The next utility bill is '
                        '"hypothetical" so a reebill can\'t be based on it'))
                new_utilbills.append(successor)
                new_utilbill_docs.append(
                        self.reebill_dao.load_doc_for_utilbill(successor))

            new_sequence = last_reebill_row.sequence + 1

        # currently only one service is supported
        assert len(new_utilbills) == 1

        # create mongo document for the new reebill, based on the documents for
        # the utility bills. discount rate and late charge rate are set to the
        # "current" values for the customer in MySQL.
        new_mongo_reebill = MongoReebill.get_reebill_doc_for_utilbills(account,
                new_sequence, 0, customer.get_discount_rate(),
                customer.get_late_charge_rate(), new_utilbill_docs)

        # create reebill row in state database
        new_reebill = ReeBill(customer, new_sequence, 0,
                utilbills=new_utilbills,
                billing_address=Address(**new_utilbill_docs[0]
                        ['billing_address']),
                service_address=Address(**new_utilbill_docs[0]
                        ['service_address']))

        # assign Reading objects to the ReeBill based on registers from the
        # utility bill document
        assert len(new_utilbill_docs) == 1
        new_reebill.replace_readings_from_utility_bill_registers(utilbill)
        session.add(new_reebill)
        session.add_all(new_reebill.readings)

        # save reebill document in Mongo
        self.reebill_dao.save_reebill(new_mongo_reebill)

        # 2nd transaction: bind and compute. if one of these fails, don't undo
        # the changes to MySQL above, leaving a Mongo reebill document without
        # a corresponding MySQL row; only undo the changes related to binding
        # and computing (currently there are none).
        if integrate_skyline_backend:
            self.ree_getter.update_renewable_readings(self.nexus_util.olap_id(account),
                                            new_reebill, use_olap=True)
            self.reebill_dao.save_reebill(new_mongo_reebill)

        if not skip_compute:
            try:
                self.compute_reebill(session, account, new_sequence)
            except Exception as e:
                self.logger.error("Error when computing reebill %s: %s" % (
                        new_reebill, e))
        return new_reebill

    def new_versions(self, session, account, sequence):
        '''Creates new versions of all reebills for 'account' starting at
        'sequence'. Any reebills that already have an unissued version are
        skipped. Returns a list of the new reebill objects.'''
        sequences = range(sequence, self.state_db.last_sequence(session,
                account) + 1)
        return [self.new_version(session, account, s) for s in sequences if
                self.state_db.is_issued(session, account, s)]

    def new_version(self, session, account, sequence):
        '''Creates a new version of the given reebill: duplicates the Mongo
        document, re-computes the bill, saves it, and increments the
        max_version number in MySQL. Returns the new MongoReebill object.'''
        customer = session.query(Customer)\
                .filter(Customer.account==account).one()

        if sequence <= 0:
            raise ValueError('Only sequence >= 0 can have multiple versions.')
        if not self.state_db.is_issued(session, account, sequence):
            raise ValueError("Can't create new version of an un-issued bill.")

        # get current max version from MySQL, and load that version's document
        # from Mongo (even if higher version exists in Mongo, it doesn't count
        # unless MySQL knows about it)
        max_version = self.state_db.max_version(session, account, sequence)
        reebill_doc = self.reebill_dao.load_reebill(account, sequence,
                version=max_version)
        reebill_doc.version = max_version + 1

        # increment max version in mysql: this adds a new reebill row with an
        # incremented version number, the same assocation to utility bills but
        # null document_id, uprs_id in the utilbill_reebill table, meaning
        # its utility bills are the current ones.
        reebill = self.state_db.increment_version(session, account, sequence)

        # replace utility bill documents with the "current" ones, and update
        # "hypothetical" utility bill data in the reebill document to match
        # (note that utility bill subdocuments in the reebill also get updated
        # in 'compute_reebill' below, but 'update_renewable_readings' won't work unless
        # they are updated)
        assert len(reebill.utilbills) == 1
        utilbill_doc = self.reebill_dao.load_doc_for_utilbill(
                reebill.utilbills[0])

        # document must be saved before update_renewable_readings is called.
        # unfortunately, this can't be undone if an exception happens.
        self.reebill_dao.save_reebill(reebill_doc)

        # update readings to match utility bill document
        reebill.replace_readings_from_utility_bill_registers(reebill.utilbill)

        # re-bind and compute
        # recompute, using sequence predecessor to compute balance forward and
        # prior balance. this is always version 0, because we want those values
        # to be the same as they were on version 0 of this bill--we don't care
        # about any corrections that might have been made to that bill later.
        self.ree_getter.update_renewable_readings(self.nexus_util.olap_id(account),
                                        reebill)

        reebill_doc = self.reebill_dao.load_reebill(reebill.customer.account,
                reebill.sequence, version=reebill.version)
        try:
            # TODO replace with compute_reebill; this is hard because the
            # document has to be saved first and it can't be saved again
            # because it has "sequence" and "version" keys
            self.compute_reebill(session, account, sequence,
                        version=max_version+1)
        except Exception as e:
            # NOTE: catching Exception is awful and horrible and terrible and
            # you should never do it, except when you can't think of any other
            # way to accomplish the same thing. ignoring the error here allows
            # a new version of the bill to be created even when it can't be
            # computed (e.g. the rate structure is broken and the user wants to
            # edit it, but can't until the new version already exists).
            self.logger.error(("In Process.new_version, couldn't compute new "
                    "version %s of reebill %s-%s: %s\n%s") % (
                    reebill_doc.version, reebill_doc.account,
                    reebill_doc.sequence, e, traceback.format_exc()))

        self.reebill_dao.save_reebill(reebill_doc)

    def get_unissued_corrections(self, session, account):
        '''Returns [(sequence, max_version, balance adjustment)] of all
        un-issued versions of reebills > 0 for the given account.'''
        result = []
        for seq, max_version in self.state_db.get_unissued_corrections(session,
                account):
            # adjustment is difference between latest version's
            # charges and the previous version's
            assert max_version > 0
            latest_version = self.state_db.get_reebill(session, account, seq,
                    version=max_version)
            prev_version = self.state_db.get_reebill(session, account, seq,
                    version=max_version - 1)
            adjustment = latest_version.total - prev_version.total
            result.append((seq, max_version, adjustment))
        return result

    def get_unissued_correction_sequences(self, session, account):
        return [c[0] for c in self.get_unissued_corrections(session, account)]

    def issue_corrections(self, session, account, target_sequence):
        '''Applies adjustments from all unissued corrections for 'account' to
        the reebill given by 'target_sequence', and marks the corrections as
        issued.'''
        # corrections can only be applied to an un-issued reebill whose version
        # is 0
        target_max_version = self.state_db.max_version(session, account,
                target_sequence)
        if self.state_db.is_issued(session, account, target_sequence) \
                or target_max_version > 0:
            raise ValueError(("Can't apply corrections to %s-%s, "
                    "because the latter is an issued reebill or another "
                    "correction.") % (account, target_sequence))
        all_unissued_corrections = self.get_unissued_corrections(session,
                account)
        if len(all_unissued_corrections) == 0:
            raise ValueError('%s has no corrections to apply' % account)

        # recompute target reebill (this sets total adjustment) and save it
        self.compute_reebill(session, account, target_sequence,
                version=target_max_version)

        # issue each correction
        for correction in all_unissued_corrections:
            correction_sequence, _, _ = correction
            self.issue(session, account, correction_sequence)

    def get_total_adjustment(self, session, account):
        '''Returns total adjustment that should be applied to the next issued
        reebill for 'account' (i.e. the earliest unissued version-0 reebill).
        This adjustment is the sum of differences in totals between each
        unissued correction and the previous version it corrects.'''
        return sum(adjustment for (sequence, version, adjustment) in
                self.get_unissued_corrections(session, account))

    def get_total_error(self, session, account, sequence):
        '''Returns the net difference between the total of the latest
        version (issued or not) and version 0 of the reebill given by account,
        sequence.'''
        earliest = self.state_db.get_reebill(session, account,
                sequence, version=0)
        latest = self.state_db.get_reebill(session, account,
                sequence, version='max')
        return latest.total - earliest.total

    def get_late_charge(self, session, reebill, day=datetime.utcnow().date()):
        '''Returns the late charge for the given reebill on 'day', which is the
        present by default. ('day' will only affect the result for a bill that
        hasn't been issued yet: there is a late fee applied to the balance of
        the previous bill when only when that previous bill's due date has
        passed.) Late fees only apply to bills whose predecessor has been
        issued; None is returned if the predecessor has not been issued. (The
        first bill and the sequence 0 template bill always have a late charge
        of 0.)'''
        acc, seq = reebill.customer.account, reebill.sequence

        if reebill.sequence <= 1:
            return 0

        # unissued bill has no late charge
        if not self.state_db.is_issued(session, acc, seq - 1):
            return None

        # late charge is 0 if version 0 of the previous bill is not overdue
        predecessor0 = self.state_db.get_reebill(session, acc, seq - 1,
                version=0)
        if day <= predecessor0.due_date:
            return 0

        # the balance on which a late charge is based is not necessarily the
        # current bill's balance_forward or the "outstanding balance": it's the
        # least balance_due of any issued version of the predecessor (as if it
        # had been charged on version 0's issue date, even if the version
        # chosen is not 0).
        max_predecessor_version = self.state_db.max_version(session, acc,
                seq - 1)
        customer = self.state_db.get_customer(session, acc)
        min_balance_due = session.query(func.min(ReeBill.balance_due))\
                .filter(ReeBill.customer == customer)\
                .filter(ReeBill.sequence == seq - 1).one()[0]
        source_balance = min_balance_due - \
                self.state_db.get_total_payment_since(session, acc,
                predecessor0.issue_date)
        #Late charges can only be positive
        return (reebill.late_charge_rate) * max(0, source_balance)

    def get_outstanding_balance(self, session, account, sequence=None):
        '''Returns the balance due of the reebill given by account and sequence
        (or the account's last issued reebill when 'sequence' is not given)
        minus the sum of all payments that have been made since that bill was
        issued. Returns 0 if total payments since the issue date exceed the
        balance due, or if no reebill has ever been issued for the customer.'''
        # get balance due of last reebill
        if sequence == None:
            sequence = self.state_db.last_issued_sequence(session, account)
        if sequence == 0:
            return 0
        reebill = self.state_db.get_reebill(account, sequence)

        if reebill.issue_date == None:
            return 0

        # result cannot be negative
        return max(0, reebill.balance_due -
                self.state_db.get_total_payment_since(session, account,
                reebill.issue_date))

    def delete_reebill(self, session, account, sequence):
        '''Deletes the the given reebill: removes the ReeBill object/row and
        its utility bill associations from MySQL, and its document from Mongo.
        A reebill version has been issued can't be deleted. Returns the version
        of the reebill that was deleted.'''
        reebill = self.state_db.get_reebill(session, account, sequence)
        if reebill.issued:
            raise IssuedBillError("Can't delete an issued reebill.")

        version = reebill.version

        # NOTE session.delete() fails with an errror like "InvalidRequestError:
        # Instance '<ReeBill at 0x353cbd0>' is not persisted" if the object has
        # not been persisted (i.e. flushed from SQLAlchemy cache to database)
        # yet; the author says on Stack Overflow to use 'expunge' if the object
        # is in 'session.new' and 'delete' otherwise, but for some reason
        # 'reebill' does not get into 'session.new' when session.add() is
        # called. i have not solved this problem yet.
        session.delete(reebill)

        # delete highest-version reebill document from Mongo
        self.reebill_dao.delete_reebill(reebill)

        # Delete the PDF associated with a reebill if it was version 0
        # because we believe it is confusing to delete the pdf when
        # when a version still exists
        if version == 0:
            full_path = self.billupload.get_reebill_file_path(account,
                    sequence)
            # If the file exists, delete it, otherwise don't worry.
            try:
                os.remove(full_path)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise
        return version

    def create_new_account(self, session, account, name, discount_rate,
            late_charge_rate, billing_address, service_address,
            template_account):
        '''Creates a new account with utility bill template copied from the
        last utility bill of 'template_account' (which must have at least one
        utility bill).
        
        'billing_address' and 'service_address' are dictionaries containing the
        addresses for the utility bill. The address format should be the
        utility bill address format.

        Returns the new state.Customer.'''
        if self.state_db.account_exists(session, account):
            raise ValueError("Account %s already exists" % account)

        last_utility_bill = session.query(UtilBill)\
            .join(Customer).filter(Customer.account == template_account)\
            .order_by(desc(UtilBill.period_end)).first()

        if last_utility_bill is None:
            raise NoSuchBillException("Last utility bill not found for account %s" % \
                                      template_account)

        new_customer = Customer(name, account, discount_rate, late_charge_rate,
                'example@example.com',
                last_utility_bill.utility,      #fb_utility_name
                last_utility_bill.rate_class,   #fb_rate_class
                Address(billing_address['addressee'],
                        billing_address['street'],
                        billing_address['city'],
                        billing_address['state'],
                        billing_address['postal_code']),
                Address(service_address['addressee'],
                        service_address['street'],
                        service_address['city'],
                        service_address['state'],
                        service_address['postal_code']))
        session.add(new_customer)
        return new_customer


# keys above for which null values should be allowed in corresponding MySQL #
# column
    def issue(self, session, account, sequence,
            issue_date=datetime.utcnow().date()):
        '''Sets the issue date of the reebill given by account, sequence to
        'issue_date' (or today by default), and the due date to 30 days from
        the issue date. The reebill's late charge is set to its permanent value
        in mongo, and the reebill is marked as issued in the state database.'''
        # version 0 of predecessor must be issued before this bill can be
        # issued:
        if sequence > 1 and not self.state_db.is_issued(session, account,
                sequence - 1, version=0):
            raise NotIssuable(("Can't issue reebill %s-%s because its "
                    "predecessor has not been issued.") % (account, sequence))


        reebill = self.state_db.get_reebill(session, account, sequence)

        # compute the bill to make sure it's up to date before issuing
        self.compute_reebill(session, reebill.customer.account,
                reebill .sequence, version=reebill.version)

        # set issue date in MySQL and due date in mongo
        reebill.issue_date = issue_date
        reebill.due_date = issue_date + timedelta(days=30)

        # set late charge to its final value (payments after this have no
        # effect on late fee)
        # TODO: should this be replaced with a call to compute_reebill to
        # just make sure everything is up-to-date before issuing?
        # https://www.pivotaltracker.com/story/show/36197985
        reebill.late_charge = self.get_late_charge(session, reebill)

        # save in mongo, creating a new frozen utility bill document, and put
        # that document's _id in the utilbill_reebill table
        # NOTE this only works when the reebill has one utility bill
        assert len(reebill._utilbill_reebills) == 1
        self._freeze_utilbill_document(session, reebill)

        # also duplicate UPRS, storing the new _ids in MySQL
        uprs = self.rate_structure_dao.load_uprs_for_utilbill(
                reebill.utilbills[0])
        uprs.id = ObjectId()
        # NOTE this is a temporary workaround for a bug in MongoEngine
        # 0.8.4 described here:
        # https://www.pivotaltracker.com/story/show/57593308
        uprs._created = True;

        uprs.save()
        reebill._utilbill_reebills[0].uprs_document_id = str(uprs.id)

        # mark as issued in mysql
        self.state_db.issue(session, account, sequence, issue_date=issue_date)

        # store email recipient in the bill
        reebill.email_recipient = reebill.customer.bill_email_recipient

    def _freeze_utilbill_document(self, session, reebill, force=False):
        '''
        Create and save a utility bill document representing the utility bill
        of the given state.ReeBill, which is about to be issued. This document
        is immutable and provides a permanent record of the utility bill
        utility bill document as it was at the time of issuing. Its _id becomes
        the "document_id" of the corresponding row in the  "utilbill_reebill"
        table in MySQL.

        Replacing an already-issued reebill (as determined by StateDB) or its
        utility bills is forbidden unless 'force' is True (this should only be
        used for testing).

        Nore: this saves changes to the reebill document in Mongo, so that
        document should be re-loaded if data are read from it after calling
        this method.
        '''
        if reebill.issued:
            raise IssuedBillError("Can't modify an issued reebill.")

        # NOTE returning the _id of the new frozen utility bill can only work
        # if there is only one utility bill; otherwise some system is needed to
        # specify which _id goes with which utility bill in MySQL
        if len(reebill.utilbills) > 1:
            raise NotImplementedError('Multiple services not yet supported')

        utilbill_doc = self.reebill_dao.load_doc_for_utilbill(
                reebill.utilbills[0])

        # convert the utility bills into frozen copies by putting
        # "sequence" and "version" keys in the utility bill, and
        # changing its _id to a new one
        new_id = bson.objectid.ObjectId()

        # copy utility bill doc so changes to it do not persist if
        # saving fails below
        utilbill_doc = copy.deepcopy(utilbill_doc)
        utilbill_doc['_id'] = new_id
        self.reebill_dao.save_utilbill(utilbill_doc, force=force,
                           sequence_and_version=(reebill.sequence,
                                                 reebill.version))
        # saving succeeded: set handle id to match the saved
        # utility bill and replace the old utility bill document with the new one
        reebill_doc = self.reebill_dao.load_reebill(reebill.customer.account,
                reebill.sequence, version=reebill.version)
        reebill_doc.reebill_dict['utilbills'][0]['id'] = new_id
        reebill._utilbill_reebills[0].document_id = new_id
        self.reebill_dao.save_reebill(reebill_doc)


    def reebill_report_altitude(self, session):
        accounts = self.state_db.listAccounts(session)
        rows = []
        totalCount = 0
        for account in accounts:
            payments = self.state_db.payments(session, account)
            cumulative_savings = 0
            for reebill_doc in self.reebill_dao.load_reebills_for(account, 0):
                # TODO using the document to load the SQLAlchemy object is
                # backwards. but ultimately the document should not be used
                # at all.
                reebill = self.reebill_dao.load_reebill(reebill_doc.account,
                        reebill_doc.sequence, reebill_doc.version)
                # Skip over unissued reebills
                if not reebill_doc.issue_date:
                    continue

                row = {}
                row['account'] = account
                row['sequence'] = reebill_doc.sequence
                row['billing_address'] = reebill_doc.billing_address
                row['service_address'] = reebill_doc.service_address
                row['issue_date'] = reebill_doc.issue_date
                row['period_begin'] = reebill_doc.period_begin
                row['period_end'] = reebill_doc.period_end
                row['actual_charges'] = reebill_doc.actual_total
                row['hypothetical_charges'] = reebill_doc.hypothetical_total
                total_ree = reebill.get_total_renewable_energy()
                row['total_ree'] = total_ree
                if total_ree != 0:
                    row['average_rate_unit_ree'] = (reebill_doc.hypothetical_total -
                            reebill_doc.actual_total)/total_ree
                else:
                    row['average_rate_unit_ree'] = 0
                row['ree_value'] = reebill_doc.ree_value
                row['prior_balance'] = reebill_doc.prior_balance
                row['balance_forward'] = reebill_doc.balance_forward
                try:
                    row['total_adjustment'] = reebill_doc.total_adjustment
                except:
                    row['total_adjustment'] = None
                row['payment_applied'] = reebill_doc.payment_received
                row['ree_charges'] = reebill_doc.ree_charges
                try:
                    row['late_charges'] = reebill_doc.late_charges
                except KeyError:
                    row['late_charges'] = None

                row['balance_due'] = reebill_doc.balance_due
                row['discount_rate'] = reebill_doc.discount_rate

                savings = reebill_doc.ree_value - reebill_doc.ree_charges
                cumulative_savings += savings
                row['savings'] = savings
                row['cumulative_savings'] = cumulative_savings

                rows.append(row)
                totalCount += 1
        return rows, totalCount

    def sequences_for_approximate_month(self, session, account, year, month):
        '''Returns a list of sequences of all reebills whose approximate month
        (as determined by dateutils.estimate_month()) is 'month' of 'year', or
        None if the month precedes the approximate month of the first reebill.
        When 'sequence' exceeds the last sequence for the account, bill periods
        are assumed to correspond exactly to calendar months.
        
        This should be the inverse of the mapping from bill periods to months
        provided by estimate_month() when its domain is restricted to months
        that actually have bills.'''
        # get all reebills whose periods contain any days in this month (there
        # should be at most 3)
        next_month_year, next_month = month_offset(year, month, 1)
        reebills = session.query(ReeBill).join(UtilBill).filter(
                UtilBill.period_start >= date(year, month, 1),
                UtilBill.period_end <= date(next_month_year, next_month, 1)
                ).all()

        # sequences for this month are those of the bills whose approximate
        # month is this month
        sequences_for_month = [r.sequence for r in reebills if
                estimate_month(r.period_begin, r.period_end) == (year, month)]

        # if there's at least one sequence, return the list of sequences
        if sequences_for_month != []:
            return sequences_for_month

        # get approximate month of last reebill (return [] if there were never
        # any reebills)
        last_sequence = self.state_db.last_sequence(session, account)
        if last_sequence == 0:
            return []
        last_reebill = self.state_db.get_reebill(account, last_sequence)
        last_reebill_year, last_reebill_month = estimate_month(
                *last_reebill.get_period())

        # if this month isn't after the last bill month, there are no bill
        # sequences
        if (year, month) <= (last_reebill_year, last_reebill_month):
            return []

        # if (year, month) is after the last bill month, return the sequence
        # determined by counting real months after the approximate month of the
        # last bill (there is only one sequence in this case)
        sequence_offset = month_difference(last_reebill_year,
                last_reebill_month, year, month)
        return [last_sequence + sequence_offset]

    def sequences_in_month(self, session, account, year, month):
        '''Returns a list of sequences of all reebills whose periods contain
        ANY days within the given month. The list is empty if the month
        precedes the period of the account's first issued reebill, or if the
        account has no issued reebills at all. When 'sequence' exceeds the last
        sequence for the account (including un-issued bills in mongo), bill
        periods are assumed to correspond exactly to calendar months. This is
        NOT related to the approximate billing month.'''
        # get all reebills whose periods contain any days in this month, and
        # their sequences (there should be at most 3)
        query_month = Month(year, month)
        sequences_for_month = session.query(ReeBill.sequence).join(UtilBill)\
                .filter(UtilBill.period_start >= query_month.first,
                UtilBill.period_end <= query_month.last).all()

        # get sequence of last reebill and the month in which its period ends,
        # which will be useful below
        last_sequence = self.state_db.last_sequence(session, account)

        # if there's at least one sequence, return the list of sequences. but
        # if query_month is the month in which the account's last reebill ends,
        # and that period does not perfectly align with the end of the month,
        # also include the sequence of an additional hypothetical reebill whose
        # period would cover the end of the month.
        if sequences_for_month != []:
            last_end = self.state_db.get_reebill(account, last_sequence
                    ).period_end
            if Month(last_end) == query_month and last_end \
                    < (Month(last_end) + 1).first:
                sequences_for_month.append(last_sequence + 1)
            return sequences_for_month

        # if there are no sequences in this month because the query_month
        # precedes the first reebill's start, or there were never any reebills
        # at all, return []
        if last_sequence == 0 or query_month.last < \
                self.state_db.get_reebill(account, 1).get_period()[0]:
            return []

        # now query_month must exceed the month in which the account's last
        # reebill ends. return the sequence determined by counting real months
        # after the approximate month of the last bill (there is only one
        # sequence in this case)
        last_reebill_end = self.state_db.get_reebill(account,
                last_sequence).get_period()[1]
        return [last_sequence + (query_month - Month(last_reebill_end))]


    def all_names_of_accounts(self, accounts):
        # get list of customer name dictionaries sorted by their billing account
        all_accounts_all_names = self.nexus_util.all_names_for_accounts(accounts)
        name_dicts = sorted(all_accounts_all_names.iteritems())

        return name_dicts

    def full_names_of_accounts(self, session, accounts):
        '''Given a list of account numbers (as strings), returns a list
        containing the "full name" of each account, each of which is of the
        form "accountnumber - codename - casualname - primus" (sorted by
        account). Names that do not exist for a given account are skipped.'''
        # get list of customer name dictionaries sorted by their billing account
        name_dicts = self.all_names_of_accounts(accounts)

        result = []
        for account, all_names in name_dicts:
            res = account + ' - '
            # Only include the names that exist in Nexus
            names = [all_names[name] for name in
                ('codename', 'casualname', 'primus')
                if all_names.get(name)]
            res += '/'.join(names)
            if len(names) > 0:
                res += ' - '
            #Append utility and rate_class from the last utilbill for the
            #account if one exists as per
            #https://www.pivotaltracker.com/story/show/58027082
            try:
                last_utilbill = self.state_db.get_last_utilbill(
                    session, account)
            except NoSuchBillException:
                #No utilbill found, just don't append utility info
                pass
            else:
                res += "%s: %s" %(last_utilbill.utility,
                last_utilbill.rate_class)
            result.append(res)
        return result

    def get_all_utilbills_json(self, session, account, start, limit):
        # result is a list of dictionaries of the form {account: account
        # number, name: full name, period_start: date, period_end: date,
        # sequence: reebill sequence number (if present)}
        utilbills, total_count = self.state_db.list_utilbills(session,
                account, start, limit)

        # this "name" is really not the name in nexus, but Stiles' creative
        # way to get utilities and rate structures shown in the "Create New
        # Account" form. luckily it's ignored by all other consumers of this
        # data.
        full_names = self.full_names_of_accounts(session, [account])
        full_name = full_names[0] if full_names else account

        data = [{
            'id': ub.id,
            'account': ub.customer.account,
            'name': full_name,
            'utility': ub.utility,
            'rate_class': ub.rate_class,
            # capitalize service name
            'service': 'Unknown' if ub.service is None else
                    ub.service[0].upper() + ub.service[1:],
            'period_start': ub.period_start,
            'period_end': ub.period_end,
            'total_charges': ub.total_charges,
            # NOTE a type-based conditional is a bad pattern; this will
            # have to go away
            'computed_total': mongo.total_of_all_charges(
                    self.reebill_dao.load_doc_for_utilbill(ub))
                    if ub.state < UtilBill.Hypothetical else None,
            # NOTE the value of 'issue_date' in this JSON object is
            # used by the client to determine whether a frozen utility
            # bill version exists (when issue date == null, the reebill
            # is unissued, so there is no frozen version of the utility
            # bill corresponding to it).
            'reebills': ub.sequence_version_json(),
            'state': ub.state_name(),
            # utility bill rows are always editable (since editing them
            # should not affect utility bill data in issued reebills)
            'processed': ub.processed,
            'editable': True,
        } for ub in utilbills]

        return data, total_count

    def bind_renewable_energy(self, session, account, sequence):
        reebill = self.state_db.get_reebill(session, account, sequence)
        self.ree_getter.update_renewable_readings(self.nexus_util.olap_id(account),
                                        reebill, use_olap=True)

    def mail_reebills(self, session, account, sequences, recipient_list):
        all_reebills = [self.state_db.get_reebill(session, account, sequence)
                for sequence in sequences]

        # render all the bills
        for reebill in all_reebills:
            the_path = self.billupload.get_reebill_file_path(account,
                    reebill.sequence)
            dirname, basename = os.path.split(the_path)
            self.renderer.render_max_version(session, reebill.customer.account,
                    reebill.sequence,
                    # self.config.get("billdb", "billpath")+ "%s" % reebill.account,
                    # "%.5d_%.4d.pdf" % (int(account), int(reebill.sequence)),
                    dirname, basename, True)

        # "the last element" (???)
        most_recent_reebill = all_reebills[-1]
        bill_file_names = ["%.5d_%.4d.pdf" % (int(account), int(sequence)) for
                sequence in sequences]
        bill_dates = ', '.join(["%s" % (b.get_period()[0])
                for b in all_reebills])
        merge_fields = {
            'street': most_recent_reebill.service_address.street,
            'balance_due': round(most_recent_reebill.balance_due, 2),
            'bill_dates': bill_dates,
            'last_bill': bill_file_names[-1],
        }
        bill_file_paths = [self.billupload.get_reebill_file_path(account,
                    s) for s in sequences]
        self.bill_mailer.mail(recipient_list, merge_fields, bill_file_paths,
                bill_file_paths)

    def get_issuable_reebills_dict(self, session):
        """ Returns a list of issuable reebill dictionaries containing
            the account, sequence, total utility bill charges, total reebill
            charges and the associated customer email address
            of the earliest unissued version-0 reebill account
        """
        unissued_v0_reebills = session.query(ReeBill.sequence, ReeBill.customer_id)\
                .filter(ReeBill.issued == 0, ReeBill.version == 0).subquery()
        min_sequence = session.query(
                unissued_v0_reebills.c.customer_id.label('customer_id'),
                func.min(unissued_v0_reebills.c.sequence).label('sequence'))\
                .group_by(unissued_v0_reebills.c.customer_id).subquery()
        reebills = session.query(ReeBill)\
                .filter(ReeBill.customer_id==min_sequence.c.customer_id)\
                .filter(ReeBill.sequence==min_sequence.c.sequence)

        issuable_reebills = sorted([{'account': r.customer.account,
                         'sequence':r.sequence,
                         'util_total': sum(u.total_charges for u in r.utilbills),
                         'mailto':r.customer.bill_email_recipient,
                         'reebill_total': sum(mongo.total_of_all_charges(ub_doc)
                                            for ub_doc in(
                                                self.reebill_dao._load_utilbill_by_id(ub_id)
                                                    for ub_id in(
                                                        u.document_id for u in r.utilbills
                                                    )
                                                )
                                          )
                         } for r in reebills.all()], key=itemgetter('account'))

        return issuable_reebills

    def update_bill_email_recipient(self, session, account, sequence, recepients):
        """ Finds a particular reebill by account and sequence,
            finds the connected customer and updates the customer's default
            email recipient(s)
        """
        reebill = self.state_db.get_reebill(session, account, sequence)
        reebill.customer.bill_email_recipient = recepients

    def upload_interval_meter_csv(self, account, sequence, csv_file,
        timestamp_column, timestamp_format, energy_column, energy_unit,
        register_identifier, **args):
        '''Takes an upload of an interval meter CSV file (cherrypy file upload
        object) and puts energy from it into the shadow registers of the
        reebill given by account, sequence. Returns reebill version number.
        '''
        reebill = self.state_db.get_reebill(account, sequence)

        # convert column letters into 0-based indices
        if not re.match('[A-Za-z]', timestamp_column):
            raise ValueError('Timestamp column must be a letter')
        if not re.match('[A-Za-z]', energy_column):
            raise ValueError('Energy column must be a letter')
        timestamp_column = ord(timestamp_column.lower()) - ord('a')
        energy_column = ord(energy_column.lower()) - ord('a')

        # extract data from the file (assuming the format of AtSite's
        # example files)
        self.ree_getter.fetch_interval_meter_data(reebill, csv_file.file,
                meter_identifier=register_identifier,
                timestamp_column=timestamp_column,
                energy_column=energy_column,
                timestamp_format=timestamp_format, energy_unit=energy_unit)
        return reebill.version

    def get_utilbill_image_path(self, session, utilbill_id, resolution):
        utilbill=self.state_db.get_utilbill_by_id(session,utilbill_id)
        return self.billupload.getUtilBillImagePath(utilbill,resolution)

    def list_account_status(self, session, start, limit, filtername, sortcol,
                            sort_reverse):
        """ Returns a list of dictonaries (containing Account, Nexus Codename,
          Casual name, Primus Name, Utility Service Address, Date of last
          issued bill, Days since then and the last event) and the length
          of the list """
        #Various filter functions used below to filter the resulting rows
        def filter_reebillcustomers(row):
            return int(row['account'])<20000
        def filter_xbillcustomers(row):
            return int(row['account'])>=20000
        # Function to format the "Utility Service Address" grid column
        def format_service_address(service_address, account):
            try:
                return '%(street)s, %(city)s, %(state)s' % service_address
            except KeyError as e:
                self.logger.error(('Utility bill service address for %s '
                        'lacks key "%s": %s') % (
                                account, e.message, service_address))
                return '?'

        statuses = self.state_db.retrieve_status_days_since(session, sortcol, sort_reverse)
        name_dicts = self.nexus_util.all_names_for_accounts([s.account for s in statuses])

        rows = []
        # To make this for loop faster we only include nexus data, status data
        # and data for the column that is sorted. After that we filter and limit
        # the rows for pagination and only after that we add all missing fields
        for status in statuses:
            new_record = {
                'account': status.account,
                'codename': name_dicts[status.account]['codename'] if
                       'codename' in name_dicts[status.account] else '',
                'casualname': name_dicts[status.account]['casualname'] if
                       'casualname' in name_dicts[status.account] else '',
                'primusname': name_dicts[status.account]['primus'] if
                'primus' in name_dicts[status.account] else '',
                'dayssince': status.dayssince,
                'provisionable': False
            }
            if sortcol=='utilityserviceaddress':
                try:
                    service_address = self.get_service_address(session,
                                                                status.account)
                    service_address=format_service_address(service_address,
                                                            status.account)
                except NoSuchBillException:
                    service_address = ''
                new_record['utilityserviceaddress']=service_address
            elif sortcol=='lastissuedate':
                last_reebill = self.state_db.get_last_reebill(session,
                     status.account, issued_only=True)
                new_record['lastissuedate'] = last_reebill.issue_date if last_reebill else ''
            rows.append(new_record)

        #Apply filters
        if filtername=="reebillcustomers":
            rows=filter(filter_reebillcustomers, rows)
        elif filtername=="xbillcustomers":
            rows=filter(filter_xbillcustomers, rows)
        rows.sort(key=itemgetter(sortcol), reverse=sort_reverse)
        total_length=len(rows)
        rows = rows[start:start+limit]

        # Add all missing fields
        for row in rows:
            row['lastevent']=self.journal_dao.last_event_summary(row['account'])
            if sortcol != 'utilityserviceaddress':
                try:
                    service_address = self.get_service_address(session,
                                                                row['account'])
                    service_address=format_service_address(service_address,
                                                            row['account'])
                except NoSuchBillException:
                    service_address = ''
                row['utilityserviceaddress']=service_address
            elif sortcol != 'lastissuedate':
                last_reebill = self.state_db.get_last_reebill(session,
                     row['account'], issued_only=True)
                row['lastissuedate'] = last_reebill.issue_date if last_reebill else ''

        return total_length, rows
