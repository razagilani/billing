'''
Main file for Bill Entry (Flask web app for y UI).utility bill data entry).
This file contains the main 'Flask' object and code for things that affect the
application as a whole, such as authentication.

Here are some recommendations on how to structure a Python/Flask project.
http://as.ynchrono.us/2007/12/filesystem-structure-of-python-project_21.html
http://flask.pocoo.org/docs/0.10/patterns/packages/
http://flask-restful.readthedocs.org/en/0.3.1/intermediate-usage.html#project
-structure
'''
import logging
import traceback
import urllib
import uuid
from urllib2 import Request, urlopen, URLError
import json
from datetime import datetime, timedelta

from celery.exceptions import ChordError, TaskRevokedError
import re
from celery.result import AsyncResult
from dateutil import tz
from sqlalchemy import desc, func
import xkcdpass.xkcd_password  as xp
from flask import Flask, url_for, request, flash, session, redirect, \
    render_template, current_app, Response, jsonify
from flask_oauth import OAuth, OAuthException
from celery import chord, group
from celery.result import GroupResult

from flask.ext.kvsession import KVSessionExtension
from flask.ext.login import LoginManager, login_user, logout_user, current_user
from flask.ext.restful import Api
from flask.ext.principal import identity_changed, Identity, AnonymousIdentity, \
    Principal, RoleNeed, identity_loaded, UserNeed, PermissionDenied
from billentry.billentry_model import BillEntryUser, Role, BEUserSession
from billentry.common import get_bcrypt_object
from billentry.resources import parse_json_extractor_field
from brokerage.brokerage_model import get_quote_status
from core import init_config, init_celery
from core.extraction import Extractor, ExtractorResult, Field
from core.extraction.applier import Applier, UtilBillApplier
from core.extraction.extraction import LayoutExtractor
from core.extraction.task import test_bill, reduce_bill_results, \
    _create_bill_file_handler
from core.model import Session, Utility, BoundingBox
from core.model.utilbill import UtilBill
from billentry import admin, resources
from exc import UnEditableBillError, MissingFileError
from util import layout

LOG_NAME = 'billentry'

app = Flask(__name__, static_url_path="")
bcrypt = get_bcrypt_object()


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
google = oauth.remote_app('google',
    base_url=config.get('billentry', 'base_url'),
    authorize_url=config.get('billentry', 'authorize_url'),
    request_token_url=config.get('billentry', 'request_token_url'),
    request_token_params={
        'scope': config.get('billentry', 'request_token_params_scope'),
        'response_type': config.get('billentry',
                                    'request_token_params_resp_type'),
        'hd': config.get('billentry', 'authorized_domain')},
    access_token_url=config.get('billentry', 'access_token_url'),
    access_token_method=config.get('billentry', 'access_token_method'),
    access_token_params={'grant_type': config.get('billentry',
                                                  'access_token_params_grant_type')},
    consumer_key=config.get('billentry', 'google_client_id'),
    consumer_secret=config.get('billentry', 'google_client_secret'))

app.secret_key = config.get('billentry', 'secret_key')
app.config['LOGIN_DISABLED'] = config.get('billentry', 'disable_authentication')

############
# KVSession
############
kvsession = KVSessionExtension(Session.bind, app)

login_manager = LoginManager()
login_manager.init_app(app)
principals = Principal(app)
app.permanent_session_lifetime = timedelta(
    seconds=config.get('billentry', 'timeout'))

if app.config['LOGIN_DISABLED']:
    login_manager.anonymous_user = BillEntryUser.get_anonymous_user

@principals.identity_loader
def load_identity_for_anonymous_user():
    if config.get('billentry', 'disable_authentication'):
        identity = AnonymousIdentity()
        identity.provides.add(RoleNeed('admin'))
        return identity


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
    return user


@app.route('/logout')
def logout():
    current_user.authenticated = False
    logout_user()
    # Remove session keys set by Flask-Principal
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)

    # Tell Flask-Principal the user is anonymous
    identity_changed.send(current_app._get_current_object(),
                          identity=AnonymousIdentity())
    flash('You Logged out successfully')
    return redirect(url_for('login_page'))


@app.route('/oauth2callback')
@google.authorized_handler
def oauth2callback(resp):
    next_url = session.pop('next_url', url_for('index'))
    if resp is None:
        # this means that the user didn't allow the OAuth provider
        # the required access, or the redirect request from the OAuth
        # provider was invalid
        return redirect(url_for('login_page'))

    session['access_token'] = resp['access_token']
    # any user who logs in through OAuth gets automatically created
    # (with a random password) if there is no existing user with
    # the same email address.
    user_email = create_user_in_db(resp['access_token'])
    user = Session().query(BillEntryUser).filter_by(email=user_email).first()
    # start keeping track of user session
    start_user_session(user)
    return redirect(next_url)


@app.route('/')
def index():
    '''this displays the home page if user is logged in
     otherwise redirects user to the login page
    '''
    response = app.send_static_file('index.html')
    # telling the client not to cache index.html prevents a problem where a
    # request for this page after logging out will appear to succeed, causing
    # the client to make AJAX requests to which the server responds with
    # redirects to the login page, causing the login page to be shown in an
    # error message window.
    response.headers['Cache-Control'] = 'no-cache'
    # If some utility bills files are uploaded, their hash-digests are
    # stored in Flask's session variable named hash-digest. If the
    # upload utility bills form is reset or the app is loaded again,
    # we need to clear those hash-digests of previously uploaded files
    # to prevent them from getting mixed with utility bills uploaded later
    if session.get('hash-digest'):
        # remove the hash-digest from session as the uploaded files are
        # irrelevant once the page is reloaded
        session.pop('hash-digest')
    return response


@app.route('/test-extractors')
def test_extractors():
    '''
    Displays a user interface for testing different bill data extractors on
    the database.
    Provides the client a list of extractors, utilities, and bill fields.
    '''
    s = Session()
    extractors = s.query(Extractor).all()
    nbills = s.query(UtilBill).count()
    utilities = s.query(Utility.name, Utility.id).distinct(Utility.name).all()
    fields = UtilBillApplier.KEYS.keys()
    return render_template('test-extractors.html', extractors=extractors,
                               nbills=nbills, utilities=utilities,
                               fields=fields)

@app.route('/get-running-tests', methods=['POST'])
def get_running_tests():
    s = Session()
    q = s.query(ExtractorResult).filter(
        ExtractorResult.finished == None)
    running_tasks = q.all()
    tasks_dict = [{
        'task_id': rt.task_id,
        'parent_id': rt.parent_id,
        'extractor_id': rt.extractor_id,
        'utility_id': rt.utility_id,
        'bills_to_run': rt.bills_to_run,
    } for rt in running_tasks]
    return jsonify({'tasks': tasks_dict})

@app.route('/run-test', methods=['POST'])
def run_test():
    """
    Runs a test of bill data extractors as an asynchronous Celery task.
    Also creates a database row in the ExtractorResult table for this test.
    :return the ID of the task being run, as well as the total number of bills
    """
    extractor_id = request.form.get('extractor_id')
    utility_id = request.form.get('utility_id')
    num_bills = int(request.form.get('num_bills'))
    date_filter_type = request.form.get('date_filter_type')
    filter_date = request.form.get('filter_date')
    #if date is just a 4-digit year, add 'january 1st' to make a full date.
    if re.match(r'\d{4}$', filter_date):
        filter_date = filter_date + "-01-01"

    s = Session();
    #get bills with valid PDF addresses, and filter by utility if necessary
    q = s.query(UtilBill.id).filter(UtilBill.sha256_hexdigest != None,
        UtilBill.sha256_hexdigest != '').order_by(
        func.random())
    if utility_id:
        q = q.filter(UtilBill.utility_id == utility_id)
    else:
        utility_id = None
    if filter_date and date_filter_type:
        if date_filter_type == 'before':
            q = q.filter(UtilBill.period_end <= filter_date)
        elif date_filter_type == 'after':
            q = q.filter(UtilBill.period_end >= filter_date)
    if num_bills > 0:
        q = q.limit(num_bills)
    if q.count() == 0:
        return jsonify({'bills_to_run':0})
    #run celery chord
    job = group([test_bill.s(extractor_id, b.id) for b in q])
    result = chord(job)(reduce_bill_results.s())
    result_parent = result.parent
    result_parent.save()
    #add task to db
    er = ExtractorResult(extractor_id=extractor_id, utility_id=utility_id,
        task_id=result.id, parent_id=result_parent.id,
        bills_to_run=q.count(), started=datetime.utcnow())
    s.add(er)
    s.commit()
    return jsonify({'task_id': result.id, 'bills_to_run': q.count()}), 202

@app.route('/test-status/<task_id>', methods=['POST'])
def test_status(task_id):
    '''
    Returns the status for a given task.
    This is done by calling reduce_bill_results on all the sub-tasks for a given task.
    :param task_id: The id of the current task
    :return: Data on the current progress of the task, including how many bills have succeeded, failed, etc.
    '''
    init_celery()

    task = AsyncResult(task_id)
    if not task.ready():
        #if task is not finished, get intermediate results:
        s = Session()
        q = s.query(ExtractorResult.parent_id).filter(
            ExtractorResult.task_id == task_id)
        parent_id = q.one().parent_id
        parent_task = GroupResult.restore(parent_id)

        subtask_results = [subtask.result for subtask in
        parent_task.results]
        response = reduce_bill_results(subtask_results)
        if response['stopped'] > 0:
            response['state'] = "STOPPED"
        elif response['failed'] > 0:
            response['state'] = "SOME SUBTASKS FAILED, IN PROGRESS"
        else:
            response['state'] = "IN PROGRESS"
        return jsonify(response)
    else:
        try:
            result = task.get()
            result['state'] = task.state
        except ChordError as tre:
            result = {'state': "STOPPED"}
        except Exception as e:
            result = {'state': "FAILURE"}
        return jsonify(result)


@app.route('/stop-task/<task_id>', methods=['POST'])
def stop_task(task_id):
    #get child tasks and revoke them
    init_celery()
    s = Session()
    q = s.query(ExtractorResult).filter(
        ExtractorResult.task_id == task_id)
    ext_res = q.one()
    parent_id = ext_res.parent_id
    # revoke chord task (i.e. the reduce step)
    AsyncResult(task_id).revoke(terminate=True, signal='SIGKILL')
    # revoke group, (i.e. all the subtasks)
    GroupResult.restore(parent_id).revoke(terminate=True, signal='SIGKILL')
    ext_res.finished = datetime.utcnow()
    s.commit()
    return "", 204

@app.route('/create-extractor/')
def create_extractor():
    """
    Serves template for the UI for creating PDF extractors
    """
    return app.send_static_file('create-extractor/app/index.html')

@app.route('/get-field-types', methods=['GET'])
def get_field_types():
    return jsonify({
        'field_types': [
            {
                'name': "Bounding Box Field",
                'mapper_id': 'boundingboxfield',
            },
            {
                'name': "Table Field",
                'mapper_id': 'tablefield',
            },]
    })

@app.route('/get-text-lines-page/<bill_id>',
    methods=['POST'],
    defaults={'min_page': None, 'max_page': None})
@app.route('/get-text-lines-page/<bill_id>/<int:min_page>',
    methods=['POST'],
    defaults={'max_page': None})
@app.route('/get-text-lines-page/<bill_id>/<int:min_page>/<int:max_page>',
    methods=['POST'])
def get_text_line(bill_id, min_page, max_page):
    """
    Return the first text object in the bill that matches 'regex'.
    The range of pages that are searched can be narrowed down with min_page
    and max_page.
    """
    regex = request.get_json()['regex']
    if not regex:
        return jsonify({'textline': None}), 200

    s = Session()
    utilbill = s.query(UtilBill).filter(UtilBill.id == bill_id).one()
    le = LayoutExtractor()
    input = le._prepare_input(utilbill,
        _create_bill_file_handler())

    if max_page is None:
        max_page = min_page
    output = None
    for p in input[0][min_page-1:max_page]:
        output = layout.get_text_line(p, regex)
        if output is None:
            continue

    if output is None:
        textline_data = None
    else:
        textline_data = {
            'text': output.text,
            'page_num': output.page_num,
            'x0': output.bounding_box.x0,
            'y0': output.bounding_box.y0,
            'x1': output.bounding_box.x1,
            'y1': output.bounding_box.y1,
        }

    return jsonify({'textline': textline_data}), 200

@app.route('/preview-field/<bill_id>', methods=['POST'])
def preview_field(bill_id):
    """
    Tests a single field on a bill.
    """
    field_json =  request.get_json()
    field = parse_json_extractor_field(field_json)

    s = Session()
    utilbill = s.query(UtilBill).filter(UtilBill.id == bill_id).one()
    le = LayoutExtractor()
    input = le._prepare_input(utilbill,
        _create_bill_file_handler())
    output = field.get_value(input)

    return jsonify({'field_output': str(output)}), 200

def create_user_in_db(access_token):
    headers = {'Authorization': 'OAuth ' + access_token}
    req = Request(config.get('billentry', 'google_user_info_url'), None,
                  headers)
    try:
        # get info about currently logged in user
        res = urlopen(req)
    except URLError, e:
        if e.code == 401:
            # Unauthorized - bad token
            session.pop('access_token', None)
            return redirect(url_for('oauth_login'))
    # TODO: display googleEmail as Username in the bottom panel
    userInfoFromGoogle = res.read()
    userInfo = json.loads(userInfoFromGoogle)
    s = Session()
    session['email'] = userInfo['email']
    user = s.query(BillEntryUser).filter_by(email=userInfo['email']).first()
    # if user coming through google auth is not already present in local
    # database, then create it in the local db and assign the 'admin' role
    # to the user for proividing access to the Admin UI.
    # This assumes that internal users are authenticating using google auth.
    if user is None:
        # generate a random password
        wordfile = xp.locate_wordfile()
        mywords = xp.generate_wordlist(wordfile=wordfile, min_length=6,
                                       max_length=8)
        user = BillEntryUser(email=session['email'],
            password=get_hashed_password(
                xp.generate_xkcdpassword(mywords, acrostic="face")))
        # add user to the admin role
        admin_role = s.query(Role).filter_by(name='admin').first()
        user.roles = [admin_role]
        s.add(user)
        s.commit()
    user.authenticated = True
    s.commit()
    # Tell Flask-Principal the identity changed
    login_user(user)
    identity_changed.send(current_app._get_current_object(),
                          identity=Identity(user.id))
    return userInfo['email']


@app.before_request
def before_request():
    if app.config['LOGIN_DISABLED']:
        return

    user = current_user
    # this is for diaplaying the nextility logo on the
    # login_page when user is not logged in
    ALLOWED_ENDPOINTS = ['oauth_login', 'oauth2callback', 'logout',
        'login_page', 'locallogin',
        # special endpoint name for all static files--not a URL
        'static']
    NON_REST_ENDPOINTS = ['admin', 'index']

    if not user.is_authenticated():
        if request.endpoint in ALLOWED_ENDPOINTS:
            return
        if (
                    request.endpoint in NON_REST_ENDPOINTS or 'admin' in
                        request.path or 'index' in request.path):
            set_next_url()
            return redirect(url_for('login_page'))
        return Response('Could not verify your access level for that URL', 401)
    if user.is_authenticated():
        update_user_session_last_request_time(user)


def update_user_session_last_request_time(user):
    """ This is called to update the last_request field of BEUserSession
    every time user makes a request for a resource
    """
    recent_session = Session.query(BEUserSession).filter_by(
        beuser=user).order_by(desc(BEUserSession.session_start)).first()
    if recent_session:
        recent_session.last_request = datetime.utcnow()
        Session.commit()


def set_next_url():
    next_path = request.args.get('next') or request.path
    if next_path:
        # Since passing along the "next" URL as a GET param requires
        # a different callback for each page, and Google requires
        # whitelisting each allowed callback page, therefore, it can't pass it
        # as a GET param. Instead, the url is sanitized and put into the
        # session.
        path = urllib.unquote(next_path)
        if path[0] == '/':
            # This first slash is unnecessary since we force it in when we
            # format next_url.
            path = path[1:]

        next_url = "{path}".format(path=path, )
        session['next_url'] = next_url


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
    # The Session.remove() method first calls Session.close() on the
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
def oauth_login():
    callback_url = url_for('oauth2callback', _external=True)
    result = google.authorize(callback=callback_url)
    return result


@app.route('/login-page')
def login_page():
    return render_template('login_page.html')


@app.errorhandler(PermissionDenied)
@app.errorhandler(OAuthException)
def page_not_found(e):
    return render_template('403.html'), 403

@app.errorhandler(MissingFileError)
@app.errorhandler(UnEditableBillError)
def uneditable_bill_error(e):
    # Flask is not supposed to run error handler functions
    # if these are true, but it does (even if they are set
    # before the "errorhandler" decorator is called).
    if (app.config['TRAP_HTTP_EXCEPTIONS'] or app.config[
        'PROPAGATE_EXCEPTIONS']):
        raise
    if isinstance(e, MissingFileError):
        error_message = log_error('MissingFileError', traceback)
    else:
        error_message = log_error('UnProcessedBillError', traceback)
    return error_message, 400


@app.errorhandler(Exception)
def internal_server_error(e):
    # Flask is not supposed to run error handler functions
    # if these are true, but it does (even if they are set
    # before the "errorhandler" decorator is called).
    if (app.config['TRAP_HTTP_EXCEPTIONS'] or app.config[
        'PROPAGATE_EXCEPTIONS']):
        raise
    error_message = log_error('Internal Server Error', traceback)

    return error_message, 500


def log_error(exception_name, traceback):
    from core import config
    # Generate a unique error token that can be used to uniquely identify the
    # errors stacktrace in a logfile
    token = str(uuid.uuid4())
    logger = logging.getLogger(LOG_NAME)
    logger.exception('Exception in BillEntry (Token: %s): ', token)
    error_message = "Internal Server Error: %s, Error Token: " \
                    "<b>%s</b>" % (exception_name, token)
    if config.get('billentry', 'show_traceback_on_error'):
        error_message += "<br><br><pre>" + traceback.format_exc() + "</pre>"
    return error_message


@app.route('/userlogin', methods=['GET', 'POST'])
def locallogin():
    email = request.form['email']
    password = request.form['password']
    user = Session().query(BillEntryUser).filter_by(email=email).first()
    if user is None:
        flash('Username or Password is invalid', 'error')
        return redirect(url_for('login_page'))
    if not check_password(password, user.password):
        flash('Username or Password is invalid', 'error')
        return redirect(url_for('login_page'))
    user.authenticated = True
    if 'rememberme' in request.form:
        login_user(user, remember=True)
    else:
        login_user(user)
    # Tell Flask-Principal the identity changed
    identity_changed.send(current_app._get_current_object(),
                          identity=Identity(user.id))
    session['user_name'] = str(user)
    start_user_session(user)
    next_url = session.pop('next_url', url_for('index'))
    return redirect(next_url)

@app.route('/quote-status')
def quote_status():
    local_tz = tz.gettz('America/New_York')
    date_format = '%a %Y-%m-%d %H:%M:%S %Z'
    format_date = lambda d: None if d is None else d.replace(
        tzinfo=tz.gettz('UTC')).astimezone(local_tz).strftime(date_format)

    return render_template('quote-status.html', data=[{
        'name': row.name,
        'date_received': format_date(row.date_received),
        'today_count': row.today_count,
        'total_count': row.total_count,
        'good': row.today_count > 0,
    } for row in get_quote_status()])

def get_hashed_password(plain_text_password):
    # Hash a password for the first time
    #   (Using bcrypt, the salt is saved into the hash itself)
    return bcrypt.generate_password_hash(plain_text_password)


def start_user_session(beuser):
    """ This method should be called after user has logged in
    to create a new BEUserSession object that keeps track of the
    duration of user's session in billentry
    """
    s = Session()
    be_user_session = BEUserSession(session_start=datetime.utcnow(),
                                    last_request=datetime.utcnow(),
                                    beuser=beuser)
    s.add(be_user_session)
    s.commit()


def check_password(plain_text_password, hashed_password):
    # Check hased password. Using bcrypt, the salt is saved into the hash itself
    return bcrypt.check_password_hash(hashed_password, plain_text_password)


class MyApi(Api):
    def handle_error(self, e):
        raise

api = MyApi(app)
api.add_resource(resources.AccountListResource, '/utilitybills/accounts')
api.add_resource(resources.AccountResource, '/utilitybills/accounts/<int:id>')
api.add_resource(resources.UtilBillListResource, '/utilitybills/utilitybills')
api.add_resource(resources.AltitudeAccountResource, '/utilitybills/altitudeaccounts')
api.add_resource(resources.UtilBillResource,
                 '/utilitybills/utilitybills/<int:id>')
api.add_resource(resources.SuppliersResource, '/utilitybills/suppliers')
api.add_resource(resources.UtilitiesResource, '/utilitybills/utilities')
api.add_resource(resources.RateClassesResource, '/utilitybills/rateclasses')
api.add_resource(resources.ChargeListResource, '/utilitybills/charges')
api.add_resource(resources.UtilityBillFileResource, '/utilitybills/uploadfile')
api.add_resource(resources.UploadUtilityBillResource, '/utilitybills/uploadbill')
api.add_resource(resources.ChargeResource, '/utilitybills/charges/<int:id>')
api.add_resource(resources.RSIBindingsResource, '/utilitybills/rsibindings')
api.add_resource(resources.UtilBillCountForUserResource,
                 '/utilitybills/users_counts')
api.add_resource(resources.UtilBillListForUserResource,
                 '/utilitybills/user_utilitybills')
api.add_resource(resources.FlaggedUtilBillListResource,
                 '/utilitybills/flagged_utilitybills')
api.add_resource(resources.ExtractorsListResource, '/extractors')
api.add_resource(resources.ExtractorResource, '/extractor/<int:id>')
api.add_resource(resources.ApplierKeyListResource, '/applier-keys')
api.add_resource(resources.FieldTypesListResource, '/field-data-types')

# apparently needed for Apache
application = app

# enable admin UI
admin.make_admin(app)
