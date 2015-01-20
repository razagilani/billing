from os.path import dirname, realpath, join

from sqlalchemy import desc

from core import init_config, init_model, init_logging


# TODO: is it necessary to specify file path?
p = join(dirname(dirname(realpath(__file__))), 'settings.cfg')
init_logging(filepath=p)
init_config(filepath=p)
init_model()

import sys

from datetime import datetime, timedelta
from util.dateutils import ISO_8601_DATE
from core.model import Session, UtilityAccount
from reebill import journal
from core.model import UtilBill

from flask import Flask
from flask.ext.restful import Api, Resource, fields, marshal_with


app = Flask(__name__)
api = Api(app)


class UtilBillResource(Resource):

    def handle_get(self, *vpath, **params):
        s = Session()
        # TODO: pre-join with Charge to make this faster, and get rid of limit
        utilbills = s.query(UtilBill).join(UtilityAccount).order_by(
            UtilityAccount.account,
                             desc(UtilBill.period_start)).limit(100).all()
        rows = [{
            'id': ub.id,
            'account': ub.utility_account.account,
            'period_start': ub.period_start,
            'period_end': ub.period_end,
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
            'next_estimated_meter_read_date': ub.period_end + timedelta(30),
            'supply_total': 0, # TODO
            'utility_account_number': ub.get_utility_account_number(),
            'secondary_account_number': '', # TODO
            'processed': ub.processed,
        } for ub in utilbills]
        return True, {'rows': rows, 'results': len(rows)}

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


class ChargesResource(Resource):

    def handle_get(self, utilbill_id, *vpath, **params):
        charges = self.utilbill_processor.get_utilbill_charges_json(utilbill_id)
        return True, {'rows': charges, 'results': len(charges)}

    def handle_put(self, charge_id, *vpath, **params):
        c = self.utilbill_processor.update_charge(cherrypy.request.json,
                                       charge_id=charge_id)
        return True, {'rows': c.column_dict(),  'results': 1}

    def handle_post(self, *vpath, **params):
        c = self.utilbill_processor.add_charge(**cherrypy.request.json)
        return True, {'rows': c.column_dict(),  'results': 1}

    def handle_delete(self, charge_id, *vpath, **params):
        self.utilbill_processor.delete_charge(charge_id)
        return True, {}


class SuppliersResource(Resource):
    def get(self):
        suppliers = self.utilbill_processor.get_all_suppliers_json()
        return True, {'rows': suppliers, 'results': len(suppliers)}
api.add_resource(SuppliersResource, '/suppliers')

class UtilitiesResource(Resource):
    def get(self):
        utilities = self.utilbill_processor.get_all_utilities_json()
        return {'rows': utilities, 'results': len(utilities)}
api.add_resource(UtilitiesResource, '/utilities')

class RateClassesResource(Resource):
    def get(self):
        rate_classes = self.utilbill_processor.get_all_rate_classes_json()
        return True, {'rows': rate_classes, 'results': len(rate_classes)}
api.add_resource(RateClassesResource, '/rateclasses')


if __name__ == '__main__':
    app.run(debug=True)

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
