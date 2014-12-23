from sqlalchemy import desc
from billing.core.model import Session, UtilBill, Register, UtilityAccount, \
    Supplier, Utility, RateClass

class UtilBillViews(object):
    '''"View" methods: return JSON dictionaries of utility bill-related data
    for ReeBill UI.
    '''
    def __init__(self, bill_file_handler):
        self.bill_file_handler = bill_file_handler

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
                                              Register.utilbill_id == UtilBill.id). \
                filter(UtilBill.id == utilbill_id).all():
            l.append(r.column_dict())
        return l

    def get_all_utilbills_json(self, account, start=None, limit=None):
        # result is a list of dictionaries of the form {account: account
        # number, name: full name, period_start: date, period_end: date,
        # sequence: reebill sequence number (if present)}
        s = Session()
        utilbills = s.query(UtilBill).join(UtilityAccount).filter_by(
            account=account).order_by(UtilityAccount.account,
                                      desc(UtilBill.period_start)).all()
        data = [dict(ub.column_dict(),
                     pdf_url=self.bill_file_handler.get_s3_url(ub))
                for ub in utilbills]
        return data, len(utilbills)

    def get_all_suppliers_json(self):
        session = Session()
        return [s.column_dict() for s in session.query(Supplier).all()]

    def get_all_utilities_json(self):
        session = Session()
        return [u.column_dict() for u in session.query(Utility).all()]

    def get_all_rate_classes_json(self):
        session = Session()
        return [r.column_dict() for r in session.query(RateClass).all()]

    def get_utility(self, name):
        session = Session()
        return session.query(Utility).filter(Utility.name == name).one()

    def get_supplier(self, name):
        session = Session()
        return session.query(Supplier).filter(Supplier.name == name).one()

    def get_rate_class(self, name):
        session = Session()
        return session.query(RateClass).filter(RateClass.name == name).one()