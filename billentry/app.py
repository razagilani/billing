'''
Main file for Bill Entry (Flask web app for y UI).utility bill data entry).
This file contains the main 'Flask' object and code for things that affect the
application as a whole, such as authentication.

Here are some recommendations on how to structure a Python/Flask project.
http://as.ynchrono.us/2007/12/filesystem-structure-of-python-project_21.html
http://flask.pocoo.org/docs/0.10/patterns/packages/
http://flask-restful.readthedocs.org/en/0.3.1/intermediate-usage.html#project-structure
'''
import urllib
from urllib2 import Request, urlopen, URLError
import json
import xkcdpass as xp

from flask import Flask, url_for, request, session, redirect
from flask.ext.login import LoginManager, login_user, logout_user, current_user
from flask.ext.restful import Api
from flask.ext.principal import identity_changed, Identity, AnonymousIdentity, Principal, Permission, RoleNeed, \
    identity_loaded, UserNeed
from flask import Flask, url_for, request, flash, session, redirect, render_template, current_app
from flask_oauth import OAuth
from billentry.billentry_model import BillEntryUser, BEUtilBill, Role

from core import init_config
from core.model import Session, UtilBill
from billentry import admin, resources


app = Flask(__name__, static_url_path="")
app.debug = True

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

app.secret_key = config.get('billentry', 'secret_key')
if config.get('billentry', 'disable_authentication'):
    app.config['TESTING'] = True
login_manager = LoginManager()
login_manager.init_app(app)
# load the extension
principals = Principal(app)

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    # Set the identity user object
    identity.user = current_user

    # Add the UserNeed to the identity
    if hasattr(current_user, 'id'):
        identity.provides.add(UserNeed(current_user.id))

    # Assuming the User model has a list of roles, update the
    # identity with the roles that the user provides
    if hasattr(current_user, 'roles'):
        for role in current_user.roles:
            identity.provides.add(RoleNeed(role.name))

@login_manager.user_loader
def load_user(id):
    user = Session().query(BillEntryUser).filter_by(id=id).first()
    if user:
        return user

@app.route('/logout')
def logout():
    session.pop('access_token', None)
    session.pop('user_name', None)
    current_user.authenticated = False
    logout_user()
    # Remove session keys set by Flask-Principal
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)

    # Tell Flask-Principal the user is anonymous
    identity_changed.send(current_app._get_current_object(),
                          identity=AnonymousIdentity())
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
    register_user(resp['access_token'])
    return redirect(next_url)

@app.route('/')
def index():
    '''this displays the home page if user is logged in
     otherwise redirects user to the login page
    '''
    return app.send_static_file('index.html')

def register_user(access_token):
    headers = {'Authorization': 'OAuth '+access_token}
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
    #TODO: display googleEmail as Username the bottom panel
    userInfoFromGoogle = res.read()
    googleEmail = json.loads(userInfoFromGoogle)
    s = Session()
    session['email'] = googleEmail['email']
    user = s.query(BillEntryUser).filter_by(email=googleEmail['email']).first()
    # if user coming through google auth is not already present in local
    # database, then create it in the local db and assign the 'admin' role
    # to the user for proividing access to the Admin UI.
    # This assumes that internal users are authenticating using google auth.
    if user is None:
        # generate a random password
        wordfile = xp.locate_wordfile()
        mywords = xp.generate_wordlist(wordfile=wordfile, min_length=6, max_length=8)
        user = BillEntryUser(email=session['email'],
                                 password=xp.generate_xkcdpassword(mywords,
                                                        acrostic="face"))
        # add user to the admin role
        admin_role = s.query(Role).filter_by(name='admin').first()
        user.roles = [admin_role]
        s.add(user)
        s.commit()
    user.authenticated = True
    s.flush()
    login_user(user)
    # Tell Flask-Principal the identity changed
    identity_changed.send(current_app._get_current_object(), identity=Identity(user.id))
    return googleEmail['email']

@app.before_request
def before_request():
    if config.get('billentry', 'disable_authentication'):
        return
    user = current_user
    # this is for diaplaying the nextility logo on the
    # login_page when user is not logged in
    if 'NEXTILITY_LOGO.png' in request.full_path:
        return app.send_static_file('images/NEXTILITY_LOGO.png')
    if not user.is_authenticated() \
            and request.endpoint not in (
            'login', 'oauth2callback', 'logout',
            'login_page', 'userlogin'):
        return redirect(url_for('login_page'))

@app.after_request
def db_commit(response):
    Session.commit()
    return response

@app.route('/login')
def login():
    set_next_url()
    return google.authorize(callback=url_for('oauth2callback', _external=True))

def set_next_url():
    next_path = request.args.get('next')
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

@app.route('/login-page')
def login_page():
    return render_template('login_page.html')

@app.route('/userlogin', methods=['GET','POST'])
def userlogin():
    email = request.form['email']
    password = request.form['password']
    user = Session().query(BillEntryUser).filter_by(email=email, password=password).first()
    if user is None:
        flash('Username or Password is invalid' , 'error')
        return redirect(url_for('login_page'))
    user.authenticated = True
    if 'rememberme' in request.form:
        login_user(user,rememberme=True)
    else:
        login_user(user)
    # Tell Flask-Principal the identity changed
    identity_changed.send(current_app._get_current_object(), identity=Identity(user.id))
    session['user_name'] = str(user)
    flash('Logged in successfully')
    return redirect(request.args.get('next') or url_for('index'))

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

