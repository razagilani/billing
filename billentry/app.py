'''
Main file for Bill Entry (Flask web app for y UI).utility bill data entry).
This file contains the main 'Flask' object and code for things that affect the
application as a whole, such as authentication.

Here are some recommendations on how to structure a Python/Flask project.
http://as.ynchrono.us/2007/12/filesystem-structure-of-python-project_21.html
http://flask.pocoo.org/docs/0.10/patterns/packages/
http://flask-restful.readthedocs.org/en/0.3.1/intermediate-usage.html#project-structure
'''
import logging
import traceback
import urllib
import uuid
from urllib2 import Request, urlopen, URLError
import json

from flask import Flask, url_for, request, session, redirect
from flask.ext.restful import Api
from flask_oauth import OAuth
from billentry.billentry_model import BEUtilBill

from core import init_config
from core.model import Session, UtilBill
from billentry import admin, resources
LOG_NAME = 'billentry'


app = Flask(__name__, static_url_path="")
# TODO: delete
#app.debug = True

# Google OAuth URL parameters MUST be configurable because the
# 'consumer_key' and 'consumer_secret' are exclusive to a particular URL,
# meaning that different instances of the application need to have different
# values of these. Therefore, the 'config' object must be read and initialized
# at module scope (an import-time side effect, and also means that
# init_test_config can't be used to provide different values instead of these).
from core import config
if config is None:
    # initialize 'config' only if it has not been initialized already (which
    # requires un-importing it and importing it again). this prevents
    # 'config' from getting re-initialized with non-test data if it was already
    # initialized with test data by calling 'init_test_config'.
    del config
    init_config()
    from core import config

oauth = OAuth()
google = oauth.remote_app(
    'google',
    base_url=config.get('billentry', 'base_url'),
    authorize_url=config.get('billentry', 'authorize_url'),
    request_token_url=config.get('billentry', 'request_token_url'),
    request_token_params={
        'scope': config.get('billentry', 'request_token_params_scope'),
        'response_type': config.get('billentry',
                                    'request_token_params_resp_type'),
        'hd': config.get('billentry', 'authorized_domain')
        },
    access_token_url=config.get('billentry', 'access_token_url'),
    access_token_method=config.get('billentry', 'access_token_method'),
    access_token_params={
        'grant_type':config.get('billentry', 'access_token_params_grant_type')},
    consumer_key=config.get('billentry', 'google_client_id'),
    consumer_secret=config.get('billentry', 'google_client_secret'))


        # TODO: there's supposed to be an option to show only bills that
        # "should be entered", i.e. BEUtilBills
        # only BEUtilBills are counted here because only they have data about
        #  when they were "entered" and who entered them.
        # TODO: there's supposed to be an option to show only bills that
        # "should be entered", i.e. BEUtilBills
        # only BEUtilBills are counted here because only they have data about
        #  when they were "entered" and who entered them.


def replace_utilbill_with_beutilbill(utilbill):
    """Return a BEUtilBill object identical to 'utilbill' except for its
    class, and delete 'utilbill' from the session. 'utilbill.id' is set to
    None because 'utilbill' no longer corresponds to a row in the database.
    Do not use 'utilbill' after passing it to this function.
    """
    assert type(utilbill) is UtilBill
    assert utilbill.discriminator == UtilBill.POLYMORPHIC_IDENTITY
    beutilbill = BEUtilBill.create_from_utilbill(utilbill)
    s = Session.object_session(utilbill)
    s.add(beutilbill)
    s.delete(utilbill)
    utilbill.id = None
    return beutilbill

# 'config' must be in scope here although it is a bad idea to read it at import
# time. see how it is initialized at the top of this file.
app.secret_key = config.get('billentry', 'secret_key')

@app.errorhandler(Exception)
def internal_server_error(e):
    from core import config
    # Generate a unique error token that can be used to uniquely identify the
    # errors stacktrace in a logfile
    token = str(uuid.uuid4())
    logger = logging.getLogger(LOG_NAME)
    logger.exception('Exception in BillEntry (Token: %s): ', token)
    error_message = "Internal Server Error. Error Token <b>%s</b>" % token
    if config.get('billentry', 'show_traceback_on_error'):
        error_message += "<br><br><pre>" + traceback.format_exc() + "</pre>"
    return error_message, 500

@app.route('/logout')
def logout():
    session.pop('access_token', None)
    return app.send_static_file('logout.html')

@app.route('/oauth2callback')
@google.authorized_handler
def oauth2callback(resp):
    next_url = session.pop('next_url', url_for('index'))
    if resp is None:
        # this means that the user didn't allow the google account
        # the required access
        return redirect(next_url)

    session['access_token'] = resp['access_token'], ''
    return redirect(next_url)

@app.route('/')
def index():
    '''this displays the home page if user is logged in
     otherwise redirects user to the login page
    '''
    from core import config
    if config.get('billentry', 'disable_google_oauth'):
        return app.send_static_file('index.html')
    access_token = session.get('access_token')

    headers = {'Authorization': 'OAuth '+access_token[0]}
    req = Request(config.get('billentry', 'google_user_info_url'),
                  None, headers)
    try:
        # get info about currently logged in user
        res = urlopen(req)
    except URLError, e:
        if e.code == 401:
            # Unauthorized - bad token
            session.pop('access_token', None)
            return redirect(url_for('login'))
    #TODO: display googleEmail as Username in the bottom panel
    userInfoFromGoogle = res.read()
    googleEmail = json.loads(userInfoFromGoogle)
    session['email'] = googleEmail['email']
    return app.send_static_file('index.html')

@app.before_request
def before_request():
    from core import config
    if config.get('billentry', 'disable_google_oauth'):
        set_next_url()
        return
    if 'access_token' not in session and request.endpoint not in (
            'login', 'oauth2callback', 'logout'):
        set_next_url()
        return redirect(url_for('login'))

@app.after_request
def db_commit(response):
    # commit the transaction after every request that should change data.
    # this might work equally well in 'teardown_appcontext' as long as it comes
    # before Session.remove().
    if request.method in ('POST', 'PUT', 'DELETE'):
        # the Admin UI calls commit() by itself, so whenever a POST/PUT/DELETE
        # request is made to the Admin UI, commit() will be called twice, but
        # the second call will have no effect.
        Session.commit()
    return response

@app.teardown_appcontext
def shutdown_session(exception=None):
    """This is called after every request (after the "after_request" callback).
    The database session is closed here following the example here:
    http://flask.pocoo.org/docs/0.10/patterns/sqlalchemy/#declarative
    """
    #The Session.remove() method first calls Session.close() on the
    # current Session, which has the effect of releasing any
    # connection/transactional resources owned by the Session first,
    # then discarding the Session itself. Releasing here means that
    # connections are returned to their connection pool and any transactional
    # state is rolled back, ultimately using the rollback() method of
    # the underlying DBAPI connection.
    # TODO: this is necessary to make the tests pass but it's not good to
    # have testing-related stuff in the main code
    if app.config['TESTING'] is not True:
        Session.remove()

@app.route('/login')
def login():
    return google.authorize(callback=url_for('oauth2callback', _external=True))

def set_next_url():
    if request.args.get('next'):
        next_path = request.args.get('next')
    else:
        next_path = request.full_path
    if next_path:
        # Since passing along the "next" URL as a GET param requires
        # a different callback for each page, and Google requires
        # whitelisting each allowed callback page, therefore, it can't pass it
        # as a GET param. Instead, the url is sanitized and put into the session.
        path = urllib.unquote(next_path)
        if path[0] == '/':
            # This first slash is unnecessary since we force it in when we
            # format next_url.
            path = path[1:]

        next_url = "{path}".format(
            path=path,)
        session['next_url'] = next_url

api = Api(app)
api.add_resource(resources.AccountResource, '/utilitybills/accounts')
api.add_resource(resources.UtilBillListResource, '/utilitybills/utilitybills')
api.add_resource(resources.UtilBillResource,
                 '/utilitybills/utilitybills/<int:id>')
api.add_resource(resources.SuppliersResource, '/utilitybills/suppliers')
api.add_resource(resources.UtilitiesResource, '/utilitybills/utilities')
api.add_resource(resources.RateClassesResource, '/utilitybills/rateclasses')
api.add_resource(resources.ChargeListResource, '/utilitybills/charges')
api.add_resource(resources.ChargeResource, '/utilitybills/charges/<int:id>')
api.add_resource(resources.UtilBillCountForUserResource, '/utilitybills/users_counts')
api.add_resource(resources.UtilBillListForUserResourece,
                 '/utilitybills/user_utilitybills/<int:id>')

# apparently needed for Apache
application = app

# enable admin UI
admin.make_admin(app)