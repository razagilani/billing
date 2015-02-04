from flask import session, url_for, redirect, request
from flask.ext.admin import AdminIndexView, expose


class MyAdminIndexView(AdminIndexView):

    @expose('/')
    def index(self):
        try:
            if session['access_token'] is None:
                return redirect(url_for('login', next=request.url))
            else:
                return super(MyAdminIndexView, self).index()
        except KeyError:
            print request.url
            return redirect(url_for('login', next=request.url))
