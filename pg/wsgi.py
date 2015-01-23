'''
Flask back-end for utility bill data-entry UI.

This file will probably have to move or split apart in order to follow
recommended file structure as documented here:
http://as.ynchrono.us/2007/12/filesystem-structure-of-python-project_21.html
http://flask.pocoo.org/docs/0.10/patterns/packages/
http://flask-restful.readthedocs.org/en/0.3.1/intermediate-usage.html#project-structure
'''
from datetime import date, datetime
from os.path import dirname, realpath, join
from boto.s3.connection import S3Connection
from flask.ext.admin.contrib.sqla import ModelView
from pg.pg_model import PGAccount

from sqlalchemy import desc

from core import initialize

from core.bill_file_handler import BillFileHandler
from core.pricing import FuzzyPricingModel
from core.utilbill_loader import UtilBillLoader
from reebill.state import ReeBillCustomer
from reebill.state import ReeBill
from reebill.utilbill_processor import UtilbillProcessor

from datetime import datetime, timedelta
from dateutil import parser as dateutil_parser
from core.model import Session, UtilityAccount, Charge, Supplier, Utility, \
    RateClass
from core.model import UtilBill

from flask import Flask, url_for
from flask.ext.restful import Api, Resource, marshal_with, marshal
from flask.ext.restful.reqparse import RequestParser
from flask.ext.restful.fields import Integer, String, Float, DateTime, Raw, \
    Boolean
from flask.ext.admin import Admin, expose, BaseView


# TODO: would be even better to make flask-restful automatically call any
# callable attribute, because no callable attributes will be normally
# formattable things like strings/numbers anyway.
class CallableField(Raw):
    '''Field type that wraps another field type: it calls the attribute,
    then formats the return value with the other field.
    '''
    def __init__(self, result_field, *args, **kwargs):
        '''
        :param result_field: field instance (not class) to format the result of
        calling the attribute.
        '''
        super(CallableField, self).__init__(*args, **kwargs)
        assert isinstance(result_field, Raw)
        self.result_field = result_field

    def format(self, value):
        return self.result_field.format(value())

class CapString(String):
    '''Like String, but first letter is capitalized.'''
    def format(self, value):
        return value.capitalize()

class IsoDatetime(Raw):
    def format(self, value):
        if value is None:
            return None
        return value.isoformat()

class BaseResource(Resource):
    '''Base class of all resources. Contains UtilbillProcessor object to be
    used in handling requests, and shared code related to JSON formatting.
    '''
    def __init__(self):
        from core import config
        s3_connection = S3Connection(
            config.get('aws_s3', 'aws_access_key_id'),
            config.get('aws_s3', 'aws_secret_access_key'),
            is_secure=config.get('aws_s3', 'is_secure'),
            port=config.get('aws_s3', 'port'),
            host=config.get('aws_s3', 'host'),
            calling_format=config.get('aws_s3', 'calling_format'))
        utilbill_loader = UtilBillLoader()
        # TODO: ugly. maybe put entire url_format in config file.
        url_format = '%s://%s:%s/%%(bucket_name)s/%%(key_name)s' % (
                'https' if config.get('aws_s3', 'is_secure') is True else
                'http', config.get('aws_s3', 'host'),
                config.get('aws_s3', 'port'))
        bill_file_handler = BillFileHandler(
            s3_connection, config.get('aws_s3', 'bucket'),
            utilbill_loader, url_format)
        pricing_model = FuzzyPricingModel(utilbill_loader)
        self.utilbill_processor = UtilbillProcessor(
            pricing_model, bill_file_handler, None)

        # field for getting the URL of the PDF corresponding to a UtilBill:
        # requires BillFileHandler, so not an attribute of UtilBill itself
        class PDFUrlField(Raw):
            def output(self, key, obj):
                return bill_file_handler.get_s3_url(obj)

        # TODO: see if these JSON formatters can be moved to classes that
        # only deal with the relevant objects (UtilBills or Charges). they're
        # here because there's more than one Resource that needs to use each
        # one (representing individual UtilBills/Charges and lists of them).
        self.utilbill_fields = {
            'id': Integer,
            'account': String,
            'period_start': IsoDatetime,
            'period_end': IsoDatetime,
            'service': CapString(default='Unknown'),
            'total_energy': CallableField(Float(),
                                          attribute='get_total_energy'),
            'total_charges': Float(attribute='target_total'),
            'computed_total': CallableField(Float(),
                                            attribute='get_total_charges'),
            # TODO: should these be names or ids or objects?
            'utility': CallableField(String(), attribute='get_utility_name'),
            'supplier': CallableField(String(), attribute='get_supplier_name'),
            'rate_class': CallableField(String(),
                                        attribute='get_rate_class_name'),
            'pdf_url': PDFUrlField,
            'service_address': String,
            'next_estimated_meter_read_date': CallableField(
                IsoDatetime(), attribute='get_estimated_next_meter_read_date',
                default=None),
            'supply_total': CallableField(Float(),
                                          attribute='get_supply_target_total'),
            'utility_account_number': CallableField(
                String(), attribute='get_utility_account_number'),
            #'secondary_account_number': '', # TODO
            'processed': Boolean,
        }

        self.charge_fields = {
            'id': Integer,
            'rsi_binding': String,
            'target_total': Float,
        }


# basic RequestParser to be extended with more arguments by each
# put/post/delete method below.
id_parser = RequestParser()
id_parser.add_argument('id', type=int, required=True)

# TODO: determine when argument to put/post/delete methods are created
# instead of RequestParser arguments

class AccountResource(BaseResource):
    def get(self):
        accounts = Session().query(UtilityAccount).join(PGAccount).order_by(
            UtilityAccount.account).all()
        return marshal(accounts, {
            'id': Integer,
            'account': String,
            'utility_account_number': String(attribute='account_number')
        })

class UtilBillListResource(BaseResource):
    def get(self):
        args = id_parser.parse_args()
        s = Session()
        # TODO: pre-join with Charge to make this faster
        utilbills = s.query(UtilBill).join(UtilityAccount).filter(
            UtilityAccount.id == args['id']).order_by(
            desc(UtilBill.period_start), desc(UtilBill.id)).all()
        rows = [marshal(ub, self.utilbill_fields) for ub in utilbills]
        return {'rows': rows, 'results': len(rows)}

class UtilBillResource(BaseResource):
    def __init__(self):
        super(UtilBillResource, self).__init__()

    def put(self, id):
        parser = id_parser.copy()
        parse_date = lambda s: dateutil_parser.parse(s).date()
        parser.add_argument('period_start', type=parse_date)
        parser.add_argument('period_end', type=parse_date)
        parser.add_argument('target_total', type=float)
        parser.add_argument('processed', type=bool)
        parser.add_argument('rate_class', type=str) # TODO: what type?
        parser.add_argument('utility', type=str) # TODO: what type?
        parser.add_argument('supplier', type=str) # TODO: what type?
        parser.add_argument('total_energy', type=float)
        parser.add_argument('service',
                            type=lambda v: None if v is None else v.lower())

        row = parser.parse_args()
        ub = self.utilbill_processor.update_utilbill_metadata(
            id,
            period_start=row['period_start'],
            period_end=row['period_end'],
            service=row['service'],
            target_total=row['target_total'],
            processed=row['processed'],
            rate_class=row['rate_class'],
            utility=row['utility'],
            supplier=row['supplier'],
            )
        if row.get('total_energy') is not None:
            ub.set_total_energy(row['total_energy'])
        self.utilbill_processor.compute_utility_bill(id)

        return {'rows': marshal(ub, self.utilbill_fields), 'results': 1}

    def delete(self, id):
        self.utilbill_processor.delete_utility_bill_by_id(id)
        return {}

class ChargeListResource(BaseResource):
    def get(self):
        parser = RequestParser()
        parser.add_argument('utilbill_id', type=int, required=True)
        args = parser.parse_args()
        utilbill = Session().query(UtilBill).filter_by(
            id=args['utilbill_id']).one()
        # TODO: return only supply charges here
        rows = [marshal(c, self.charge_fields) for c in utilbill.charges]
        return {'rows': rows, 'results': len(rows)}

class ChargeResource(BaseResource):

    def put(self, id=None):
        parser = id_parser.copy()
        parser.add_argument('rsi_binding', type=str)
        parser.add_argument('target_total', type=float)
        args = parser.parse_args()

        s = Session()
        charge = s.query(Charge).filter_by(id=id).one()
        if 'rsi_binding' in args:
            # convert name to all caps with underscores instead of spaces
            charge.rsi_binding = args['rsi_binding'].strip().upper().replace(
                ' ', '_')
        if 'target_total' in args:
            charge.target_total = args['target_total']
        s.commit()
        return {'rows': marshal(charge, self.charge_fields), 'results': 1}

    def post(self, id):
        # TODO: client sends "id" even when its value is meaningless (the
        # value is always 0, for some reason)
        parser = id_parser.copy()
        parser.add_argument('utilbill_id', type=int, required=True)
        parser.add_argument('rsi_binding', type=str, required=True)
        args = parser.parse_args()
        charge = self.utilbill_processor.add_charge(
            args['utilbill_id'], rsi_binding=args['rsi_binding'])
        Session().commit()
        return {'rows': marshal(charge, self.charge_fields), 'results': 1}

    def delete(self, id):
        self.utilbill_processor.delete_charge(id)
        Session().commit()
        return {}

class SuppliersResource(BaseResource):
    def get(self):
        suppliers = Session().query(Supplier).all()
        rows = marshal(suppliers, {'id': Integer, 'name': String})
        return {'rows': rows, 'results': len(rows)}

class UtilitiesResource(BaseResource):
    def get(self):
        utilities = Session().query(Utility).all()
        rows = marshal(utilities, {'id': Integer, 'name': String})
        return {'rows': rows, 'results': len(rows)}

class RateClassesResource(BaseResource):
    def get(self):
        rate_classes = self.utilbill_processor.get_all_rate_classes_json()
        rows = marshal(rate_classes, {'id': Integer, 'name': String})
        return {'rows': rows, 'results': len(rows)}

if __name__ == '__main__':
    initialize()

    app = Flask(__name__)
    api = Api(app)
    api.add_resource(AccountResource, '/utilitybills/accounts')
    api.add_resource(UtilBillListResource, '/utilitybills/utilitybills')
    api.add_resource(UtilBillResource, '/utilitybills/utilitybills/<int:id>')
    api.add_resource(SuppliersResource, '/utilitybills/suppliers')
    api.add_resource(UtilitiesResource, '/utilitybills/utilities')
    api.add_resource(RateClassesResource, '/utilitybills/rateclasses')
    api.add_resource(ChargeListResource, '/utilitybills/charges')
    api.add_resource(ChargeResource, '/utilitybills/charges/<int:id>')

    admin = Admin(app)

    admin.add_view(ModelView(UtilityAccount, Session()))
    admin.add_view(ModelView(UtilBill, Session(), name='Utility Bill'))
    admin.add_view(ModelView(Utility, Session()))
    admin.add_view(ModelView(Supplier, Session()))
    admin.add_view(ModelView(RateClass, Session()))
    admin.add_view(ModelView(ReeBillCustomer, Session(),
                   name='ReeBill Account'))
    admin.add_view(ModelView(ReeBill, Session(), name='Reebill'))

    app.run(debug=True)
