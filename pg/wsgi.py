from datetime import date, datetime
from os.path import dirname, realpath, join
from boto.s3.connection import S3Connection

from sqlalchemy import desc

from core import init_config, init_model, init_logging, config

from core.bill_file_handler import BillFileHandler
from core.pricing import FuzzyPricingModel
from core.utilbill_loader import UtilBillLoader
from reebill.utilbill_processor import UtilbillProcessor

from datetime import datetime, timedelta
from core.model import Session, UtilityAccount, Charge
from core.model import UtilBill

from flask import Flask, url_for
from flask.ext.restful import Api, Resource, marshal_with, marshal
from flask.ext.restful.reqparse import RequestParser
from flask.ext.restful.fields import Integer, String, Float, DateTime, Raw, \
    Boolean


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

class CapitalizedString(String):
    '''Like String, but first letter is capitalized.'''
    def format(self, value):
        return value.capitalize()

class DateIsoformat(Raw):
    def format(self, value):
        return value.isoformat()

class MyResource(Resource):
    def __init__(self):
        init_config()
        init_model()
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
        self.bill_file_handler = BillFileHandler(
            s3_connection, config.get('aws_s3', 'bucket'),
            utilbill_loader, url_format)
        pricing_model = FuzzyPricingModel(utilbill_loader)
        self.utilbill_processor = UtilbillProcessor(
            pricing_model, self.bill_file_handler, None)


    # fields that require special behavior:
    # - pdf_url is a different callable that is different for each utility
    # bill, therefore can't use CallableField
    utilbill_fields = {
        'id': Integer,
        'account': String,
        'period_start': DateIsoformat,
        'period_end': DateIsoformat,
        'service': CapitalizedString(default='Unknown'),
        'total_energy': CallableField(Float(), attribute='get_total_energy'),
        'total_charges': Float(attribute='target_total'),
        'computed_total': CallableField(Float(), attribute='get_total_charges'),
        # TODO: should these be names or ids or objects?
        'utility': CallableField(String(), attribute='get_utility_name'),
        'supplier': CallableField(String(), attribute='get_suuplier_name'),
        'rate_class': CallableField(String(), attribute='get_rate_class_name'),
        # TODO:
        #'pdf_url': self.bill_file_handler.get_s3_url(ub),
        'service_address': String,
        # TODO
        'next_estimated_meter_read_date': CallableField(
            DateIsoformat(), attribute='get_estimated_next_meter_read_date',
            default=None),
        #'supply_total': 0, # TODO
        'utility_account_number': CallableField(
            String(), attribute='get_utility_account_number'),
        #'secondary_account_number': '', # TODO
        'processed': Boolean,
        }

# TODO: remove redundant parser code
# http://flask-restful.readthedocs.org/en/0.3.1/reqparse.html#parser-inheritance

class UtilBillListResource(MyResource):
    def get(self):
        s = Session()
        # TODO: pre-join with Charge to make this faster, and get rid of limit
        utilbills = s.query(UtilBill).join(UtilityAccount).order_by(
            UtilityAccount.account,
            desc(UtilBill.period_start)).limit(100).all()
        rows = [marshal(ub, self.utilbill_fields) for ub in utilbills]
        return {'rows': rows, 'results': len(rows)}

class UtilBillResource(MyResource):
    def __init__(self):
        super(UtilBillResource, self).__init__()

    def put(self, id):
        parser = RequestParser()
        parser.add_argument('id', type=int, required=True)
        parser.add_argument('period_start', type=date)
        parser.add_argument('period_end', type=date)
        parser.add_argument('target_total', type=float)
        parser.add_argument('processed', type=bool)
        parser.add_argument('rate_class', type=str) # TODO: what type?
        parser.add_argument('utility', type=str) # TODO: what type?
        parser.add_argument('supplier', type=str) # TODO: what type?
        parser.add_argument('total_energy', type=float)
        parser.add_argument('service', type=str)

        row = parser.parse_args()
        ub = self.utilbill_processor.update_utilbill_metadata(
            id,
            period_start=row['period_start'],
            period_end=row['period_end'],
            service=None if row['service'] is None else row['service'].lower(),
            target_total=row['target_total'],
            processed=row['processed'],
            rate_class=row['rate_class'],
            utility=row['utility'],
            supplier=row['supplier'],
            )
        if 'total_energy' in row:
            ub.set_total_energy(row['total_energy'])
        self.utilbill_processor.compute_utility_bill(id)

        return {'rows': marshal(ub, self.utilbill_fields), 'results': 1}

    def delete(self, id):
        utilbill, deleted_path = self.utilbill_processor.delete_utility_bill_by_id(
            id)
        # journal.UtilBillDeletedEvent.save_instance(
        #     cherrypy.session['user'], utilbill.get_nextility_account_number(),
        #     utilbill.period_start, utilbill.period_end,
        #     utilbill.service, deleted_path)
        return {}



class ChargeListResource(MyResource):
    def __init__(self):
        super(ChargeListResource, self).__init__()
        self.parser = RequestParser()
        self.parser.add_argument('utilbill_id', type=int, required=True)

    def get(self):
        args = self.parser.parse_args()
        utilbill = Session().query(UtilBill).filter_by(
            id=args['utilbill_id']).one()
        charges = [{
            'id': charge.id,
            'rsi_binding': charge.rsi_binding,
            # TODO
            'target_total': 0, #charge.target_total,
        } for charge in utilbill.charges]
        return {'rows': charges, 'results': len(charges)}

class ChargeResource(MyResource):
    def __init__(self):
        super(ChargeResource, self).__init__()
        self.parser = RequestParser()
        self.parser.add_argument('id', type=int, required=True)
        self.parser.add_argument('rsi_binding', type=str)
        self.parser.add_argument('target_total', type=float)

    def put(self, id):
        args = self.parser.parse_args()
        s = Session()
        charge = s.query(Charge).filter_by(id=id).one()
        for key in ('rsi_binding', 'target_total'):
            value = args[key]
            if value is not None:
                setattr(charge, key, value)
        s.commit()
        return {'rows': {
            'id': charge.id,
            'rsi_binding': charge.rsi_binding,
            # TODO
            'target_total': 0, #charge.target_total,
        }, 'results': 1}

    def post(self, id):
        # TODO: client sends "id" even when its value is meaningless (the
        # value is always 0, for some reason)
        self.parser.add_argument('utilbill_id', type=int, required=True)
        args = self.parser.parse_args()
        charge = self.utilbill_processor.add_charge(
            args['utilbill_id'], rsi_binding=args['rsi_binding'])
        Session().commit()
        return {'rows': {
            'id': charge.id,
            'rsi_binding': charge.rsi_binding,
            # TODO
            'target_total': 0, #charge.target_total,
            }, 'results': 1}

    def delete(self, id):
        self.utilbill_processor.delete_charge(id)
        Session().commit()
        return {}


class SuppliersResource(MyResource):
    def get(self):
        suppliers = self.utilbill_processor.get_all_suppliers_json()
        return {'rows': suppliers, 'results': len(suppliers)}

class UtilitiesResource(MyResource):
    def get(self):
        utilities = self.utilbill_processor.get_all_utilities_json()
        return {'rows': utilities, 'results': len(utilities)}

class RateClassesResource(MyResource):
    def get(self):
        rate_classes = self.utilbill_processor.get_all_rate_classes_json()
        print rate_classes
        return {'rows': rate_classes, 'results': len(rate_classes)}

if __name__ == '__main__':
    p = join(dirname(dirname(realpath(__file__))), 'settings.cfg')
    init_logging(filepath=p)
    init_config(filepath=p)
    init_model()

    app = Flask(__name__)
    api = Api(app)
    api.add_resource(UtilBillListResource, '/utilitybills/utilitybills')
    api.add_resource(UtilBillResource, '/utilitybills/utilitybills/<int:id>')
    api.add_resource(SuppliersResource, '/utilitybills/suppliers')
    api.add_resource(UtilitiesResource, '/utilitybills/utilities')
    api.add_resource(RateClassesResource, '/utilitybills/rateclasses')
    api.add_resource(ChargeListResource, '/utilitybills/charges')
    api.add_resource(ChargeResource, '/utilitybills/charges/<int:id>')

    app.run(debug=True)
