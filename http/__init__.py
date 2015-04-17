from flask.app import Flask
from flask.ext.mako import MakoTemplates
from flask.ext.wtf.csrf import CsrfProtect
from billing import config
from http.view.powergas import *

routes = [('/quotes', 'quotes', quotes),
          ('/quote/<quote_id>', 'quote_view', quote_view),
          ('/offer/<offer_id>', 'offer_view', offer_view),
          ('/interest', 'customer_interest', customer_interest),
          ('/interest/new/edit', 'interest_new', interest_edit, {'defaults': {'interest_id': 'new'}}),
          ('/interest/<interest_id>/edit', 'interest_edit', interest_edit, {'methods': ['GET', 'POST']}),
          ('/interest/<interest_id>', 'interest_view', interest_view),
          ('/interest/<interest_id>/generate_offers', 'generate_offers', generate_offers),
          ('/dummydata', 'dummy_data', dummy_data)]

def make_flask_app():
    """Construct and return a Flask WSGI Application"""

    app = Flask('billing',
                static_url_path='/static',
                static_folder=config.get('main', 'appdir') + '/billing/http/static',
                template_folder=config.get('main', 'appdir') + '/billing/http/template')

    app.config['MAKO_IMPORTS'] = ['from flask_login import current_user',
                    'from flask_wtf.csrf import generate_csrf as csrf_token']
    app.config['PROPAGATE_EXCEPTIONS'] = False
    app.config['MAKO_TRANSLATE_EXCEPTIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.secret_key = config.get('http', 'secret_key')

    MakoTemplates(app)
    CsrfProtect(app)

    for route in routes:
        d = route[3] if len(route) > 3 else {}
        app.add_url_rule(*route[0:3], **d)

    return app
