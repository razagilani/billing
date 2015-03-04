'''
Flask back-end for utility bill data-entry UI.

This file will probably have to move or split apart in order to follow
recommended file structure as documented here:
http://as.ynchrono.us/2007/12/filesystem-structure-of-python-project_21.html
http://flask.pocoo.org/docs/0.10/patterns/packages/
http://flask-restful.readthedocs.org/en/0.3.1/intermediate-usage.html#project-structure
'''
from datetime import datetime
import urllib
from urllib2 import Request, urlopen, URLError
import json

from flask import Flask, url_for, request, session, redirect
from flask.ext.restful import Api
from flask_oauth import OAuth

from core import init_config
from core.model import Session
from brokerage.billentry import resources, admin


oauth = OAuth()

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

google = oauth.remote_app(
    'google',
    base_url=config.get('billentry', 'base_url'),
    authorize_url=config.get('billentry', 'authorize_url'),
    request_token_url=config.get('billentry', 'request_token_url'),
    request_token_params={
        'scope': config.get('billentry', 'request_token_params_scope'),
        'response_type': config.get('billentry',
                                    'request_token_params_resp_type'),
        },
    access_token_url=config.get('billentry', 'access_token_url'),
    access_token_method=config.get('billentry', 'access_token_method'),
    access_token_params={
        'grant_type':config.get('billentry', 'access_token_params_grant_type')},
    consumer_key=config.get('billentry', 'google_client_id'),
    consumer_secret=config.get('billentry', 'google_client_secret'))


class ChargeResource(BaseResource):

    def put(self, id=None):
        parser = id_parser.copy()
        parser.add_argument('rsi_binding', type=str)
        parser.add_argument('target_total', type=float)
        args = parser.parse_args()

        s = Session()
        charge = s.query(Charge).filter_by(id=id).one()
        if args['rsi_binding'] is not None:
            # convert name to all caps with underscores instead of spaces
            charge.rsi_binding = args['rsi_binding'].strip().upper().replace(
                ' ', '_')
        if args['target_total'] is not None:
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
        rate_classes = Session.query(RateClass).all()
        rows = marshal(rate_classes, {
            'id': Integer,
            'name': String,
            'utility_id': Integer})
        return {'rows': rows, 'results': len(rows)}

class UtilBillCountForUserResource(BaseResource):

    def get(self, *args, **kwargs):
        parser = RequestParser()
        # parser.add_argument('start', type=dateutil_parser.parse, required=True)
        # parser.add_argument('end', type=dateutil_parser.parse, required=True)
        parser.add_argument('start', type=str, required=True)
        parser.add_argument('end', type=str, required=True)
        args = parser.parse_args()
        # TODO: for some reason, it does not work to use type=dateutil_parser.parse here, even though that does work above in a PUT request.
        start = dateutil_parser.parse(args['start'])
        end = dateutil_parser.parse(args['end'])

        s = Session()
        utilbill_sq = s.query(BEUtilBill.id,
                              BEUtilBill.billentry_user_id).filter(
            and_(BEUtilBill.billentry_date >= start,
                 BEUtilBill.billentry_date < end)).subquery()
        q = s.query(BillEntryUser, func.count(utilbill_sq.c.id)).outerjoin(
            utilbill_sq).group_by(BillEntryUser.id).order_by(BillEntryUser.id)
        rows = [{
            'user_id': user.id,
            'count': count,
        } for (user, count) in q.all()]
        return {'rows': rows, 'results': len(rows)}

class UtilBillListForUserResourece(BaseResource):
    """List of bills queried by id of BillEntryUser who "entered" them.
    """
    def get(self, id=None):
        assert isinstance(id, int)
        s = Session()
        utilbills = s.query(BEUtilBill).join(BillEntryUser).filter(
            BillEntryUser.id == id).order_by(desc(UtilBill.period_start),
                                             desc(UtilBill.id)).all()
        rows = [marshal(ub, self.utilbill_fields) for ub in utilbills]
        return {'rows': rows, 'results': len(rows)}

app = Flask(__name__, static_url_path="")
app.debug = True

# 'config' must be in scope here although it is a bad idea to read it at import
# time. see how it is initialized at the top of this file.
app.secret_key = config.get('billentry', 'secret_key')

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
    if access_token is None:
        # user is not logged in so redirect to login page
        return redirect(url_for('login'))

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
    #TODO: display googleEmail as Username the bottom panel
    userInfoFromGoogle = res.read()
    googleEmail = json.loads(userInfoFromGoogle)
    session['email'] = googleEmail['email']
    return app.send_static_file('index.html')

@app.before_request
def before_request():
    from core import config
    if config.get('billentry', 'disable_google_oauth'):
        return
    if 'access_token' not in session and request.endpoint not in (
            'login', 'oauth2callback', 'logout'):
        return redirect(url_for('login'))

@app.after_request
def db_commit(response):
    Session.commit()
    return response

@app.route('/login')
def login():
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
    return google.authorize(callback=url_for('oauth2callback', _external=True))

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
api.add_resource(UtilBillCountForUserResource, '/utilitybills/users_counts')
api.add_resource(UtilBillListForUserResourece,
                 '/utilitybills/user_utilitybills/<int:id>')

# apparently needed for Apache
application = app

# enable admin UI
admin.make_admin(app)

