from django.contrib import admin
from django import forms
from django.shortcuts import redirect
from django.conf.urls import patterns
from django.core.urlresolvers import reverse_lazy
from intro.models import *

class StateAdmin(admin.ModelAdmin):
    list_display = ('abbr', 'name', 'brokerage_possible', 'id')
    list_display_links = ('id', 'abbr', 'name')
    list_filter = ['brokerage_possible']
    search_fields = ['abbr', 'name']


class AddressAdmin(admin.ModelAdmin):
    list_display = ('street1', 'street2', 'city', 'state', 'zip', 'id')
    list_display_links = ('id', 'street1', 'street2', 'city', 'state', 'zip')
    search_fields = ['street1', 'street2', 'city', 'state__name', 'zip']


class AccountAdminForm(forms.ModelForm):
    class Meta:
        model = Account

    def clean_token(self):
        return self.cleaned_data['token'] or None

    def clean_guid(self):
        return self.cleaned_data['guid'] or None

    def clean_tou_signed(self):
        return self.cleaned_data['tou_signed'] or None

    def clean_first_name(self):
        return self.cleaned_data['first_name'] or None


class AccountAdmin(admin.ModelAdmin):
    form = AccountAdminForm
    list_display = ('name',  'guid', 'modified', 'created', 'id')
    list_display_links = ('id', 'name', 'guid')
    search_fields = ['name', 'guid']

    def get_form(self, request, obj=None, **kwargs):
        form = super(AccountAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['tou_signed'].initial = None
        form.base_fields['token'].initial = None
        form.base_fields['guid'].initial = None
        form.base_fields['name'].initial = None
        return form


class UserAdmin(admin.ModelAdmin):
    exclude = ('password', 'identifier', 'groups', 'user_permissions')
    list_display = (
        'email_address', 'first_name', 'last_name', 'account',
        'email_verified', 'is_admin', 'user_state',
        'last_login', 'modified', 'created', 'id')
    list_display_links = ('id', 'email_address', 'first_name',
                          'last_name')
    list_filter = ['email_address_verified', 'is_admin', 'user_state']
    search_fields = ['email_address', 'first_name', 'last_name',
                     'account__name', 'account__guid']

    def email_verified(self, obj):
        return obj.email_address_verified
    email_verified.boolean = True
    email_verified.admin_order_field = 'email_address_verified'


class TokenAdmin(admin.ModelAdmin):
    list_display = ('token', 'purpose', 'user', 'created', 'expires', 'id')
    list_filter = ['user', 'created', 'expires']
    list_display_links = ('id', 'token', 'purpose')
    search_fields = ['user__email_address', 'token']


class UtilityProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'state',
                    'supported_services', 'type','modified',
                    'created', 'id', 'guid')
    search_fields = ['name', 'state__name', 'state__abbr']


class UtilityWebsiteInformationForm(forms.ModelForm):
    class Meta:
        model = UtilityWebsiteInformation
        exclude = ['utility_username', 'utility_password']

    utility_username_decrypted = forms.CharField(max_length=64,
                                                 label="Utility Username",
                                                 required=False)
    utility_password_decrypted = forms.CharField(max_length=64,
                                                 label="Utility Password",
                                                 required=False)


class UtilityWebsiteInformationAdmin(admin.ModelAdmin):
    form = UtilityWebsiteInformationForm
    list_display = (
        'get_account_name', 'get_account_guid', 'utility_username_decrypted',
        'utility_password_decrypted',
        'utility_provider', 'comments', 'modified', 'created', 'id')
    list_display_links = ('id', 'get_account_name', 'get_account_guid',
                         'utility_username_decrypted',
                          'utility_password_decrypted')
    search_fields = ['accounts__name', 'accounts__guid', 'accounts__token',
                     'utility_provider__name', 'comments']

    def get_account_guid(self, obj):
        return ', '.join(
            [str(a.guid) for a in obj.accounts.all() if a.guid]
        )
    get_account_guid.short_description = 'Account GUID(s)'

    def get_account_name(self, obj):
        return ', '.join([str(a) for a in obj.accounts.all()])
    get_account_name.short_description = 'Account(s)'

    def get_form(self, request, obj=None, **kwargs):
        form = super(UtilityWebsiteInformationAdmin, self).get_form(request,
                                                                    obj,
                                                                    **kwargs)
        if obj is not None:
            form.declared_fields[
                'utility_username_decrypted'].initial = obj.get_username()
            form.declared_fields[
                'utility_password_decrypted'].initial = obj.get_password()
        else:
            form.declared_fields[
                'utility_username_decrypted'].initial = ''
            form.declared_fields[
                'utility_password_decrypted'].initial = ''
        return form

    def save_model(self, request, obj, form, change):
        obj.set_username(form.cleaned_data.get('utility_username_decrypted'))
        obj.set_password(form.cleaned_data.get('utility_password_decrypted'))
        obj.save()


admin.site.register(State, StateAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(User, UserAdmin)
admin.site.register(Token, TokenAdmin)
admin.site.register(UtilityProvider, UtilityProviderAdmin)
admin.site.register(UtilityWebsiteInformation, UtilityWebsiteInformationAdmin)
