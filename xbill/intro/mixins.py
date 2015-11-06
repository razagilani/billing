from django.http import Http404
from django.utils.translation import ugettext as _
from django.utils import timezone
from django.views.generic.edit import FormMixin, ProcessFormView
from django.views.generic.list import ListView
from braces.views import LoginRequiredMixin
from extra_views import FormSetView
from django.views.generic import TemplateView, View, RedirectView, FormView
from utils.log import get_client_id
from forms import *
from models import *
import logging
import json
from django.template import Template

log = logging.getLogger('xbill')


class RequestTypeMixin(object):
    page_content = None

    def get_context_data(self, **kwargs):
        context = super(RequestTypeMixin, self).get_context_data(**kwargs)
        # if self.request.is_ajax():
        #     context['requesttype_base'] = 'json_base.html'
        # else:
        #     context['requesttype_base'] = 'base.html'
        context['requesttype_base'] = 'base.html'

        # For dynamic content
        if self.page_content is not None:
            try:
                context['content_template'] = Template(
                    Content.get_last_version(self.page_content).content)
            except Content.DoesNotExist:
                context['content_template'] = Template('')
        else:
            context['content_template'] = Template('')

        return context

    # def render_to_response(self, context, **response_kwargs):
    #     # if self.request.is_ajax():
    #     #     response_kwargs.update({'content_type': 'application/json'})
    #     #     # We need to include the requested path in the response header
    #     #     # so in case the json request gets redirected the browser
    #     #     # still knows what page he would be on if this was a regular
    #     #     # request. We update the hash according to this header
    #     #     # with jQuery.
    #     #     response = super(RequestTypeMixin, self).render_to_response(
    #     #         context, **response_kwargs)
    #     #     response['X-XBill-requestPath'] = self.request.get_full_path()
    #     #     return response
    #     # else:
    #         return super(RequestTypeMixin, self).render_to_response(
    #             context, **response_kwargs)




class RequestTypeTemplateView(RequestTypeMixin, TemplateView):
    pass


class DashboardMixin(RequestTypeMixin, LoginRequiredMixin):
    dashboard_panel = None

    def get_context_data(self, **kwargs):
        context = super(DashboardMixin, self).get_context_data(**kwargs)
        dashboard_data = {}
        context['dashboardData'] = dashboard_data
        if self.request.is_ajax():
            if self.request.META['HTTP_X_XBILL_REQUESTSCOPE'] == 'body':
                context[
                    'requesttype_dashboard_base'] = \
                    'dashboard/html_dashboard_base.html'
                context['requesttype_base'] = 'json_base.html'
                context['json_scope'] = '#js-block-content'
            else:
                context[
                    'requesttype_dashboard_base'] = \
                    'dashboard/json_dashboard_base.html'
                context['requesttype_base'] = None
        else:
            context[
                'requesttype_dashboard_base'] = \
                'dashboard/html_dashboard_base.html'
            context['requesttype_base'] = 'base.html'
        return context

    def dispatch(self, request, *args, **kwargs):
        self.template_name = 'dashboard/' + self.dashboard_panel
        return super(DashboardMixin, self).dispatch(request, *args, **kwargs)


class DashboardTemplateView(DashboardMixin, TemplateView):
    pass

class FormSetListView(FormSetView, ListView):
    def prepare_response(self):
        self.formset = self.construct_formset()
        # From BaseListView
        self.object_list = self.get_queryset()
        allow_empty = self.get_allow_empty()
        if not allow_empty and len(self.object_list) == 0:
            raise Http404(
                _(u"Empty list and '%(class_name)s.allow_empty' is False.")
                % {'class_name': self.__class__.__name__})

    def get(self, request, *args, **kwargs):
        self.prepare_response()
        context = self.get_context_data(object_list=self.object_list,
                                        formset=self.formset)
        return self.render_to_response(context)

    def formset_invalid(self, formset):
        self.prepare_response()
        context = self.get_context_data(object_list=self.object_list,
                                        form=self.formset)
        return self.render_to_response(context)


class RequestFormView(FormView):
    def get_form_kwargs(self):
        kwargs = super(RequestFormView, self).get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class TokenMixin(object):
    # Python's super is weird but super useful for writing mixins:
    # http://www.robgolding.com/blog/2012/07/12/django-class-based-view-mixins-part-1/
    # https://fuhm.net/super-harmful/
    token_purpose = ''
    token_status = 'invalid'
    # Possible options for token_delete: 'never', 'expired', 'valid', 'both'
    #   both: delete on both expired and valid
    token_delete = 'never'

    def dispatch(self, request, *args, **kwargs):
        if request.method.lower() == 'get':
            try:
                self.token = Token.objects.select_related('user').get(
                    token=kwargs.get('token'),
                    purpose=self.token_purpose)
                email_address = self.token.user.email_address
                # Save the email address of the related user
                # and the last token in the session
                self.request.session['email'] = email_address
                self.request.session['last_token'] = self.token.token
                if self.token.expires > timezone.now():
                    # Expiry date is in the future
                    self.token_status = "valid"
                else:
                    self.token_status = "expired"
            except Token.DoesNotExist:
                self.token_status = "invalid"
        elif request.method.lower() == 'post':
            t = self.request.session.get('last_token')
            try:
                self.token = Token.objects.select_related('user')\
                    .get(token=t, purpose=self.token_purpose)
                if self.token.expires > timezone.now():
                    # Expiry date is in the future
                    self.token_status = "valid"
                else:
                    self.token_status = "expired"
            except Token.DoesNotExist:
                self.token_status = "invalid"
            # If the token_delete == token_status or 'both' then delete
        if self.token_status != "invalid":
            if self.token_delete in (self.token_status, 'both'):
                log.info("Token %s was deleted." % self.token)
                self.token.delete()

        return super(TokenMixin, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(TokenMixin, self).get_context_data(**kwargs)
        context['token_status'] = self.token_status
        return context
