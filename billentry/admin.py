"""Code to set up the "Admin" UI for the billing database, using Flask-Admin.
This lets people view or edit anythihg in the database and has nothing to do
with Bill Entry, but it's part of Bill Entry because that is currently the
only application that uses Flask.
"""
from flask import session, url_for, redirect, request
from flask.ext.admin import AdminIndexView, expose, Admin
from flask.ext.admin.contrib.sqla import ModelView
from core.model import Supplier, Utility, RateClass, UtilityAccount, Session, \
    UtilBill
from reebill.state import ReeBillCustomer, ReeBill


class MyAdminIndexView(AdminIndexView):

    @expose('/')
    def index(self):
        from core import config
        try:
            if config.get('billentry', 'disable_google_oauth'):
                return super(MyAdminIndexView, self).index()
            if session['access_token'] is None:
                return redirect(url_for('login', next=request.url))
            return super(MyAdminIndexView, self).index()
        except KeyError:
            print request.url
            return redirect(url_for('login', next=request.url))

class CustomModelView(ModelView):
    # Disable create, update and delete on model
    can_create = False
    can_delete = False
    can_edit = False

    def is_accessible(self):
        from core import config
        try:
            if config.get('billentry', 'disable_google_oauth'):
                return True
            elif session['access_token'] is None:
                return False
            return True
        except KeyError:
            return False

    def _handle_view(self, name, **kwargs):
        if not self.is_accessible():
            return redirect(url_for('login', next=request.url))

    def __init__(self, model, session, **kwargs):
        super(CustomModelView, self).__init__(model, session, **kwargs)

class LoginModelView(ModelView):
    def is_accessible(self):
        from core import config
        try:
            if config.get('billentry', 'disable_google_oauth'):
                return True
            elif session['access_token'] is None:
                return False
            return True
        except KeyError:
            return False

    def _handle_view(self, name, **kwargs):
        if not self.is_accessible():
            return redirect(url_for('login', next=request.url))

    def __init__(self, model, session, **kwargs):
        super(LoginModelView, self).__init__(model, session, **kwargs)

class SupplierModelView(LoginModelView):
    form_columns = ('name',)

    def __init__(self, session, **kwargs):
        super(SupplierModelView, self).__init__(Supplier, session, **kwargs)

class UtilityModelView(LoginModelView):
    form_columns = ('name',)

    def __init__(self, session, **kwargs):
        super(UtilityModelView, self).__init__(Utility, session, **kwargs)

class ReeBillCustomerModelView(LoginModelView):
    form_columns = (
        'name', 'discountrate', 'latechargerate', 'bill_email_recipient',
        'service', )

    def __init__(self, session, **kwargs):
        super(ReeBillCustomerModelView, self).__init__(ReeBillCustomer, session,
                                                       **kwargs)

class RateClassModelView(LoginModelView):

    def __init__(self, session, **kwargs):
        super(RateClassModelView, self).__init__(RateClass, session, **kwargs)


def make_admin(app):
    '''Return a new Flask 'Admin' object associated with 'app' representing
    the admin UI.
    '''
    admin = Admin(app, index_view=MyAdminIndexView())
    admin.add_view(CustomModelView(UtilityAccount, Session))
    admin.add_view(CustomModelView(UtilBill, Session, name='Utility Bill'))
    admin.add_view(UtilityModelView(Session))
    admin.add_view(SupplierModelView(Session))
    admin.add_view(RateClassModelView(Session))
    admin.add_view(ReeBillCustomerModelView(Session, name='ReeBill Account'))
    admin.add_view(CustomModelView(ReeBill, Session, name='Reebill'))
    return admin
