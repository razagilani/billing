from flask.app import Flask
from billing import config

def make_flask_app():
    app = Flask('billing')
    app.config['MAKO_IMPORTS'] = ['from flask_login import current_user',
                    'from flask_wtf.csrf import generate_csrf as csrf_token']
    app.config['PROPAGATE_EXCEPTIONS'] = False
    app.config['MAKO_TRANSLATE_EXCEPTIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.secret_key = config.get('http', 'secret_key')
    return app
