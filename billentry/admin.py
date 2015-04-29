"""Code to set up the "Admin" UI for the billing database, using Flask-Admin.
This lets people view or edit anythihg in the database and has nothing to do
with Bill Entry, but it's part of Bill Entry because that is currently the
only application that uses Flask.
"""
from flask import session, url_for, redirect, request
from flask.ext.admin import AdminIndexView, expose, Admin
from flask.ext import login
from flask.ext.admin.contrib.sqla import ModelView
from flask.ext.principal import Permission, RoleNeed
from core.model import Supplier, Utility, RateClass, UtilityAccount, Session, UtilBill
from billentry.billentry_model import BillEntryUser, Role, RoleBEUser
from reebill.reebill_model import ReeBillCustomer, ReeBill, CustomerGroup
from billentry.common import get_bcrypt_object



# Create a permission with a single Need, in this case a RoleNeed.
admin_permission = Permission(RoleNeed('admin'))
bcrypt = get_bcrypt_object()

class MyAdminIndexView(AdminIndexView):

    @expose('/')
    def index(self):
        from core import config
        if config.get('billentry', 'disable_authentication'):
                return super(MyAdminIndexView, self).index()
        if login.current_user.is_authenticated():
            with admin_permission.require():
                return super(MyAdminIndexView, self).index()
        return redirect(url_for('login', next=request.url))


class CustomModelView(ModelView):
    # Disable create, update and delete on model
    can_create = False
    can_delete = False
    can_edit = False

    def is_accessible(self):
        from core import config
        if config.get('billentry', 'disable_authentication'):
            return True
        return login.current_user.is_authenticated()

    def _handle_view(self, name, **kwargs):
        if not self.is_accessible():
            return redirect(url_for('login', next=request.url))

    def __init__(self, model, session, **kwargs):
        super(CustomModelView, self).__init__(model, session, **kwargs)


class LoginModelView(ModelView):
    def is_accessible(self):
        from core import config
        if config.get('billentry', 'disable_authentication'):
            return True
        return login.current_user.is_authenticated()

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

# it is not necessary to create a subclass just to create one instance of
# LoginModelView with certain arguments!
customer_group_model_view = LoginModelView(CustomerGroup, Session,
                                           name='ReeBill Customer Group')

class UserModelView(LoginModelView):
    form_columns = ('email', 'password', )

    def __init__(self, session, **kwargs):
        super(UserModelView, self).__init__(BillEntryUser, session, **kwargs)

    def on_model_change(self, form, model, is_created):
        model.password = self.get_hashed_password(model.password)

    def get_hashed_password(self, plain_text_password):
        # Hash a password for the first time
        #   (Using bcrypt, the salt is saved into the hash itself)
        return bcrypt.generate_password_hash(plain_text_password)


def make_admin(app):
    '''Return a new Flask 'Admin' object associated with 'app' representing
    the admin UI.
    '''
    admin = Admin(app, index_view=MyAdminIndexView())
    admin.add_view(CustomModelView(UtilityAccount, Session))
    admin.add_view(CustomModelView(UtilBill, Session, name='Utility Bill'))
    admin.add_view(UtilityModelView(Session))
    admin.add_view(SupplierModelView(Session))
    admin.add_view(LoginModelView(RateClass, Session))
    admin.add_view(UserModelView(Session))
    admin.add_view(LoginModelView(Role, Session, name= 'BillEntry Role'))
    admin.add_view(LoginModelView(RoleBEUser, Session, name='BillEntry User Role'))
    admin.add_view(ReeBillCustomerModelView(Session, name='ReeBill Account'))
    admin.add_view(CustomModelView(ReeBill, Session, name='Reebill'))
    admin.add_view(customer_group_model_view)
    return admin
