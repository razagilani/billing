"""All the code for serializing data into JSON for the ReeBill UI. If any
code for that is still in other files it should be moved here.
"""
from sqlalchemy import desc, and_
from sqlalchemy.sql import functions as func
from sqlalchemy.orm import joinedload
from core.model import Session, Register, UtilityAccount, \
    Supplier, Utility, RateClass, SupplyGroup, Charge
from core.model.utilbill import UtilBill
from reebill.reebill_model import ReeBill, ReeBillCustomer, ReeBillCharge, CustomerGroup


ACCOUNT_NAME_REGEX = '[0-9a-z]{5}'

def column_dict(self):
    return {c: getattr(self, c) for c in self.column_names()}

def column_dict_utilbill(self):
    result = {c: getattr(self, c) for c in self.column_names()}
    # human-readable names for utilbill states (used in UI)
    state_name = {
        UtilBill.Complete: 'Final',
        UtilBill.UtilityEstimated: 'Utility Estimated',
        UtilBill.Estimated: 'Estimated',
        }[self.state]
    result = dict(result.items() +
                  [('account', self.utility_account.account),
                   ('service', 'Unknown' if self.get_service() is None
                   else self.get_service().capitalize()),
                   ('total_charges', self.target_total),
                   ('computed_total', self.get_total_charges()),
                   ('reebills', [ur.reebill.column_dict() for ur
                                 in self._utilbill_reebills]),
                   ('utility', self.utility.name),
                   ('utility_id', self.utility_id),
                   ('supplier', self.get_supplier_name()),
                   ('supplier_id', self.supplier_id),
                   ('rate_class', self.get_rate_class_name()),
                   ('rate_class_id', self.rate_class_id),
                   ('supply_group', self.get_supply_group_name()),
                   ('supply_group_id', self.supply_group_id),
                   ('state', state_name)])
    return result

class Views(object):
    '''"View" methods: return JSON dictionaries of utility bill-related data
    for ReeBill UI.
    '''
    def __init__(self, reebill_dao, bill_file_handler, nexus_util, journal_dao):
        # TODO: it would be good to avoid using database/network connections
        # in here--data from these should be passed in by the caller so
        # these methods only handle transforming the data into JSON for display
        self._reebill_dao = reebill_dao
        self._bill_file_handler = bill_file_handler
        self._nexus_util = nexus_util
        self._journal_dao = journal_dao

    def get_utilbill_charges_json(self, utilbill_id):
        """Returns a list of dictionaries of charges for the utility bill given
        by  'utilbill_id' (MySQL id)."""
        session = Session()
        utilbill = session.query(UtilBill).filter_by(id=utilbill_id).one()
        return [column_dict(charge) for charge in utilbill.charges]

    def get_registers_json(self, utilbill_id):
        """Returns a dictionary of register information for the utility bill
        having the specified utilbill_id."""
        l = []
        session = Session()
        for r in session.query(Register).join(
                UtilBill).filter(UtilBill.id == utilbill_id).all():
            l.append(column_dict(r))
        return l

    def get_utilbill_json(self, utilbill):
        return column_dict_utilbill(utilbill)

    def get_register_json(self, register):
        return column_dict(register)

    def get_charge_json(self, charge):
        return column_dict(charge)

    def get_rate_class_json(self, rate_class):
        return column_dict(rate_class)

    def get_supplier_json(self, supplier):
        return column_dict(supplier)

    def get_utility_json(self, utility):
        return column_dict(utility)

    def get_supply_group_json(self, supply_group):
        return column_dict(supply_group)

    def get_all_utilbills_json(self, account, start=None, limit=None):
        # result is a list of dictionaries of the form {account: account
        # number, name: full name, period_start: date, period_end: date,
        # sequence: reebill sequence number (if present)}
        s = Session()
        utilbills = s.query(UtilBill).join(UtilityAccount).filter_by(
            account=account).order_by(UtilityAccount.account,
                                      desc(UtilBill.period_start)).all()
        data = [dict(column_dict_utilbill(ub),
                     pdf_url=self._bill_file_handler.get_url(ub))
                for ub in utilbills]
        return data, len(utilbills)

    def _serialize_id_name(self, class_):
        """JSON serialization for suppliers, utilities, rate classes, ...
        """
        return [dict(id=x.id, name=x.name) for x in
                Session().query(class_).order_by(class_.name).all()]

    def get_all_suppliers_json(self):
        return self._serialize_id_name(Supplier)

    def get_all_customer_groups_json(self):
        return  self._serialize_id_name(CustomerGroup)

    def get_all_utilities_json(self):
        return [dict(id=x.id, name=x.name,
                     sos_supplier_id_=x.sos_supplier_id) for x in
                Session().query(Utility).order_by(Utility.name).all()]

    def get_all_rate_classes_json(self):
        return [dict(id=x.id, name=x.name,
                     utility_id=x.utility_id, service=x.service) for x in
                Session().query(RateClass).order_by(RateClass.name).all()]

    def get_all_supply_groups_json(self):
        return [dict(id=x.id, name=x.name,
                     supplier_id=x.supplier_id,
                     service=x.service) for x in
                Session().query(SupplyGroup).order_by(SupplyGroup.name).all()]

    def get_utility(self, name):
        session = Session()
        return session.query(Utility).filter(Utility.name == name).one()

    def get_supplier(self, name):
        session = Session()
        return session.query(Supplier).filter(Supplier.name == name).one()

    def get_rate_class(self, name):
        session = Session()
        return session.query(RateClass).filter(RateClass.name == name).one()

    def get_all_rsi_bindings(self):
        rsi_bindings = Session.query(Charge.rsi_binding).distinct().all()
        return [dict(name=rsi_binding[0]) for rsi_binding in rsi_bindings]

    def list_account_status(self, account=None):
        """ Returns a list of dictonaries (containing Account, Nexus Codename,
          Casual name, Primus Name, Utility Service Address, payee, Date of last
          issued bill, Days since then and the last event) and the length
          of the list for all accounts. If account is given, the only the
          accounts dictionary is returned """
        session = Session()
        utility_accounts = session.query(
            UtilityAccount, ReeBillCustomer).outerjoin(
            ReeBillCustomer).options(joinedload('utilbills')).options(
            joinedload('fb_utility')).options(joinedload('fb_rate_class'))

        if account is not None:
            utility_accounts = utility_accounts.filter(
                UtilityAccount.account == account)

        rows_dict = {}
        for ua, reebill_customer in utility_accounts:
            name_dict = self._nexus_util.fast_all('billing', ua.account)
            if reebill_customer is None:
                group_names = []
                payee = ''
            else:
                group_names = ','.join(g.name for g in reebill_customer.groups)
                payee = reebill_customer.payee
            rows_dict[ua.account] = {
                'account': ua.account,
                'utility_account_id': ua.id,
                'fb_utility_name': ua.fb_utility.name,
                'fb_rate_class': ua.fb_rate_class.name \
                    if ua.fb_rate_class else '',
                'utility_account_number': ua.account_number,
                'codename': name_dict.get('codename', ''),
                'casualname': name_dict.get('casualname', ''),
                'primusname': name_dict.get('primus', ''),
                'utilityserviceaddress': str(ua.get_service_address()),
                'tags': group_names,
                'lastevent': '',
                'payee': payee
            }

        if account is not None:
            events = [(account, self._journal_dao.last_event_summary(account))]
        else:
            events = self._journal_dao.get_all_last_events()
        for acc, last_event in events:
            # filter out events that belong to an unknown account (this could
            # not be done in JournalDAO.get_all_last_events() because it only
            # has access to Mongo)
            if acc in rows_dict:
                rows_dict[acc]['lastevent'] = last_event

        rows = list(rows_dict.itervalues())
        return len(rows), rows

    # TODO: no test coverage
    def list_all_versions(self, account, sequence):
        ''' Returns all Reebills with sequence and account ordered by versions
            a list of dictionaries
        '''
        session = Session()
        q = session.query(ReeBill).join(ReeBillCustomer) \
            .join(UtilityAccount).with_lockmode('read') \
            .filter(UtilityAccount.account == account) \
            .filter(ReeBill.sequence == sequence) \
            .order_by(desc(ReeBill.version))

        return [rb.column_dict() for rb in q]

    def get_reebill_metadata_json(self, account):
        """Returns data describing all reebills for the given account, as list
        of JSON-ready dictionaries.
        """
        session = Session()
        def _get_total_error(account, sequence):
            '''Returns the net difference between the total of the latest
            version (issued or not) and version 0 of the reebill given by
            account, sequence.
            '''
            earliest = session.query(ReeBill).join(ReeBillCustomer).join(
                UtilityAccount).filter(UtilityAccount.account == account,
                                          ReeBill.sequence == sequence,
                                          ReeBill.version == 0).one()
            latest = session.query(ReeBill).join(ReeBillCustomer).join(
                UtilityAccount).filter(UtilityAccount.account == account,
                                          ReeBill.sequence == sequence
            ).order_by(desc(ReeBill.version)).first()
            return latest.total - earliest.total

        # this subquery gets (customer_id, sequence, version) for all the
        # reebills whose version is the maximum in their (customer, sequence,
        # version) group.
        latest_versions_sq = session.query(
            ReeBill.reebill_customer_id, ReeBill.sequence,
            func.max(ReeBill.version).label('max_version')) \
            .join(ReeBillCustomer).join(UtilityAccount) \
            .filter(UtilityAccount.account == account) \
            .order_by(ReeBill.reebill_customer_id,
                      ReeBill.sequence).group_by(
            ReeBill.reebill_customer_id,
            ReeBill.reebill_customer, ReeBill.sequence).subquery()

        # query ReeBill joined to the above subquery to get only
        # maximum-version bills, and also outer join to ReeBillCharge to get
        # sum of 0 or more charges associated with each reebill
        q = session.query(ReeBill).join(latest_versions_sq, and_(
            ReeBill.reebill_customer_id ==
            latest_versions_sq.c.reebill_customer_id,
            ReeBill.sequence == latest_versions_sq.c.sequence,
            ReeBill.version == latest_versions_sq.c.max_version)
        ).outerjoin(ReeBillCharge) \
            .order_by(desc(ReeBill.sequence)).group_by(ReeBill.id)

        return [
            dict(rb.column_dict().items(),
                total_error=_get_total_error(account, rb.sequence),
                estimated=rb.is_estimated())
        for rb in q]

    def get_issuable_reebills_dict(self):
        """ Returns a list of issuable reebill dictionaries
            of the earliest unissued version-0 reebill account. If
            proccessed == True, only processed Reebills are returned
            account can be used to get issuable bill for an account
        """
        return [r.column_dict() for r in
                self._reebill_dao.get_issuable_reebills().all()]