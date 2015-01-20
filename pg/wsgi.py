from os.path import dirname, realpath, join
from boto.s3.connection import S3Connection

from sqlalchemy import desc

from core import init_config, init_model, init_logging, config


# TODO: is it necessary to specify file path?
from core.bill_file_handler import BillFileHandler
from core.pricing import FuzzyPricingModel
from core.utilbill_loader import UtilBillLoader
from reebill.utilbill_processor import UtilbillProcessor

p = join(dirname(dirname(realpath(__file__))), 'settings.cfg')
init_logging(filepath=p)
init_config(filepath=p)
init_model()

import sys

from datetime import datetime, timedelta
from util.dateutils import ISO_8601_DATE, date_to_datetime
from core.model import Session, UtilityAccount, Charge
from reebill import journal
from core.model import UtilBill

from flask import Flask, url_for
from flask.ext.restful import Api, Resource, fields, marshal_with
from flask.ext.restful.reqparse import RequestParser


app = Flask(__name__)
api = Api(app)

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

class UtilBillResource(MyResource):

    def get(self):
        s = Session()
        # TODO: pre-join with Charge to make this faster, and get rid of limit
        utilbills = s.query(UtilBill).join(UtilityAccount).order_by(
            UtilityAccount.account,
                             desc(UtilBill.period_start)).limit(100).all()
        rows = [{
            'id': ub.id,
            'account': ub.utility_account.account,
            'period_start': ub.period_start.isoformat(),
            'period_end': ub.period_end.isoformat(),
            'service': 'Unknown' if ub.service is None
            else ub.service.capitalize(),
            'total_energy': ub.get_total_energy(),
            'total_charges': ub.target_total,
            'computed_total': ub.get_total_charges(),
            'computed_total': 0,
            # TODO: should these be names or ids or objects?
            'utility': ub.get_utility_name(),
            'supplier': ub.get_supplier_name(),
            'rate_class': ub.get_rate_class_name(),
            'pdf_url': self.bill_file_handler.get_s3_url(ub),
            'service_address': str(ub.service_address),
            'next_estimated_meter_read_date': (ub.period_end + timedelta(
                30)).isoformat(),
            'supply_total': 0, # TODO
            'utility_account_number': ub.get_utility_account_number(),
            'secondary_account_number': '', # TODO
            'processed': ub.processed,
        } for ub in utilbills]
        return {'rows': rows, 'results': len(rows)}

    def handle_put(self, utilbill_id, *vpath, **params):
        row = cherrypy.request.json
        action = row.pop('action')
        result= {}

        if action == 'regenerate_charges':
            ub = self.utilbill_processor.regenerate_uprs(utilbill_id)
            result = ub.column_dict()

        elif action == 'compute':
            ub = self.utilbill_processor.compute_utility_bill(utilbill_id)
            result = ub.column_dict()

        elif action == '': 
            result = self.utilbill_processor.update_utilbill_metadata(
                utilbill_id,
                period_start=datetime.strptime(row['period_start'], ISO_8601_DATE).date(),
                period_end=datetime.strptime(row['period_end'], ISO_8601_DATE).date(),
                service=row['service'].lower(),
                target_total=row['target_total'],
                processed=row['processed'],
                rate_class=row['rate_class'],
                utility=row['utility'],
                supplier=row['supplier'],
                ).column_dict()
            if 'total_energy' in row:
                ub = Session().query(UtilBill).filter_by(id=utilbill_id).one()
                ub.set_total_energy(row['total_energy'])
            self.utilbill_processor.compute_utility_bill(utilbill_id)

        # Reset the action parameters, so the client can coviniently submit
        # the same action again
        result['action'] = ''
        result['action_value'] = ''
        return True, {'rows': result, 'results': 1}

    def handle_delete(self, utilbill_id, *vpath, **params):
        utilbill, deleted_path = self.utilbill_processor.delete_utility_bill_by_id(
            utilbill_id)
        journal.UtilBillDeletedEvent.save_instance(
            cherrypy.session['user'], utilbill.get_nextility_account_number(),
            utilbill.period_start, utilbill.period_end,
            utilbill.service, deleted_path)
        return True, {}



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

api.add_resource(UtilBillResource, '/utilitybills/utilitybills')
api.add_resource(SuppliersResource, '/utilitybills/suppliers')
api.add_resource(UtilitiesResource, '/utilitybills/utilities')
api.add_resource(RateClassesResource, '/utilitybills/rateclasses')
api.add_resource(ChargeListResource, '/utilitybills/charges')
api.add_resource(ChargeResource, '/utilitybills/charges/<int:id>')


if __name__ == '__main__':
    app.run(debug=True)
    url_for('static', filename='index.html')

    # class CherryPyRoot(object):
    #     utilitybills = app

    #ui_root = join(dirname(realpath(__file__)), 'ui')
    # cherrypy_conf = {
    #     '/': {
    #         'tools.sessions.on': True,
    #         'request.methods_with_bodies': ('POST', 'PUT', 'DELETE')
    #     },
    #     '/utilitybills/index.html': {
    #         'tools.staticfile.on': True,
    #         'tools.staticfile.filename': join(ui_root, "index.html")
    #     },
    #     '/utilitybills/static': {
    #         'tools.staticdir.on': True,
    #         'tools.staticdir.dir': join(ui_root, "static")
    #     },
    # }
    #
    # cherrypy.config.update({
    #     'server.socket_host': app.config.get("reebill", "socket_host"),
    #     'server.socket_port': app.config.get("reebill", "socket_port")})
    # cherrypy.log._set_screen_handler(cherrypy.log.access_log, False)
    # cherrypy.log._set_screen_handler(cherrypy.log.access_log, True,
    #                                  stream=sys.stdout)
    # cherrypy.quickstart(CherryPyRoot(), "/", config=cherrypy_conf)
else:
    # WSGI Mode
    ui_root = join(dirname(realpath(__file__)), 'ui')
    cherrypy_conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': ui_root,
            'request.methods_with_bodies': ('POST', 'PUT', 'DELETE')
        },
        '/login.html': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "login.html")
        },
        '/index.html': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "index.html")
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': 'static'
        },
        '/static/revision.txt': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': join(ui_root, "../../revision.txt")
        }

    }
    cherrypy.config.update({
        'environment': 'embedded',
        'tools.sessions.on': True,
        'tools.sessions.timeout': 240,
        'request.show_tracebacks': True

    })

    if cherrypy.__version__.startswith('3.0') and cherrypy.engine.state == 0:
        cherrypy.engine.start()
        atexit.register(cherrypy.engine.stop)
    application = cherrypy.Application(
        ReebillWSGI(), script_name=None, config=cherrypy_conf)
