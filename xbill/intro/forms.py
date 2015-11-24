from django import forms
from xbill import settings
from intro.models import *
from django.contrib.auth.hashers import check_password
from django.contrib.auth import authenticate


class WelcomeForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.select_fields = []
        select_count = kwargs.pop('selectCount', 1)
        super(WelcomeForm, self).__init__(*args, **kwargs)
        for i in xrange(0, select_count):
            #Only the first field is required
            f = forms.ModelChoiceField(
                queryset=State.objects.all(),
                label="In which states are your properties located?",
                empty_label="No Properties", required=(not i))
            self.fields['stateselect' + str(i)] = f
            #For the ollowing refer to the code
            #https://github.com/django/django/blob/master/django/forms/forms.py
            #self.select_fields is supposed to work like self.visible_fields
            #self.visible_fields is a list of boundfields
            #bound field are fields with additional information
            #like HTML rendering 
            bf = forms.forms.BoundField(self, f, 'stateselect' + str(i))
            self.select_fields.append(bf)

    email = forms.EmailField(label="E-mail Address", max_length=80)
    selectCount = forms.IntegerField(widget=forms.HiddenInput())

    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            User.objects.get(email_address=email)
            raise forms.ValidationError(
                "This E-mail address is already registered! \
                 Did you forget your password?")
        except User.DoesNotExist:
            return email


class LoginForm(forms.Form):
    email = forms.EmailField(label="E-mail Address", max_length=80)
    password = forms.CharField(widget=forms.PasswordInput(), label="Password",
                               min_length=8)
    rememberme = forms.BooleanField(label="Remember Me", required=False)

    def clean(self):
        cleaned_data = super(LoginForm, self).clean()
        email_address = cleaned_data.get('email')
        password = cleaned_data.get('password')
        if email_address and password:
            user = authenticate(email_address=email_address, password=password)
            if user is not None:
                if user.is_active:
                    cleaned_data["user"] = user
                else:
                    #The account was disabled
                    raise forms.ValidationError("Your account was disabled."
                                                " Please contact the system \
                                                administrator if you believe \
                                                that this is the result of a \
                                                mistake.")
            else:
                #The username/password is not correct
                raise forms.ValidationError(
                    "The E-mail Address/Password combination was wrong")
        return cleaned_data


class EnterEmailForm(forms.Form):
    email1 = forms.EmailField(label="E-mail Address", max_length=80)
    email2 = forms.EmailField(label="Repeat your E-mail Address", max_length=80)

    def clean(self):
        cleaned_data = super(EnterEmailForm, self).clean()
        email1 = cleaned_data.get('email1')
        email2 = cleaned_data.get('email2')
        if (email1 != email2) and (email1 and email2):
            raise forms.ValidationError("Your email addresses did not match")
        return cleaned_data


class ForgotPasswordForm(EnterEmailForm):
    def clean(self):
        cleaned_data = super(ForgotPasswordForm, self).clean()
        email1 = cleaned_data.get('email1')
        email2 = cleaned_data.get('email2')
        try:
            User.objects.get(email_address=email1)
        except User.DoesNotExist:
            raise forms.ValidationError("This E-mail address is not registered")
        if (email1 != email2) and (email1 and email2):
            raise forms.ValidationError("Your email addresses did not match")
        return cleaned_data


class EnterPasswordForm(forms.Form):
    password1 = forms.CharField(widget=forms.PasswordInput(),
                                label="New Password", min_length=8)
    password2 = forms.CharField(widget=forms.PasswordInput(),
                                label="Reenter new Password", min_length=8)

    def clean(self):
        cleaned_data = super(EnterPasswordForm, self).clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 != password2:
            raise forms.ValidationError("Your passwords did not match")
        return cleaned_data


class ChangePasswordForm(EnterPasswordForm):
    def __init__(self, request, *args, **kwargs):
        self.request = request
        self.post = request.POST
        super(ChangePasswordForm, self).__init__(*args, **kwargs)

    oldpassword = forms.CharField(widget=forms.PasswordInput(),
                                  label="Current Password")

    def clean_oldpassword(self):
        if not check_password(self.cleaned_data.get('oldpassword'),
                              self.request.user.password):
            self._errors['oldpassword'] = u'Your password was incorrect'
            raise forms.ValidationError("Your password was incorrect")


class UserAccountInformationForm(forms.Form):
    def __init__(self, request, *args, **kwargs):
        self.request = request
        self.post = request.POST
        super(UserAccountInformationForm, self).__init__(*args, **kwargs)

    first_name = forms.CharField(label="First Name", max_length=40)
    last_name = forms.CharField(label="Last Name", max_length=40)
    email1 = forms.EmailField(label="E-mail Address", max_length=80)
    email2 = forms.EmailField(label="Repeat your E-mail Address", max_length=80)

    def clean_email1(self):
        email = self.cleaned_data.get('email1')
        try:
            tmpuser = User.objects.get(email_address=email)
            if self.request.user != tmpuser:
                raise forms.ValidationError(
                    "This E-Mail Address is alread registered. Did you forget \
                    your password?")
        except User.DoesNotExist:
            pass
        return email

    def clean(self):
        cleaned_data = super(UserAccountInformationForm, self).clean()
        email1 = cleaned_data.get('email1')
        email2 = cleaned_data.get('email2')
        if (email1 != email2) and (email1 and email2):
            raise forms.ValidationError("Your email addresses did not match")
        return cleaned_data


class SignupForm(UserAccountInformationForm):
    password1 = forms.CharField(widget=forms.PasswordInput(),
                                label="New Password", min_length=8)
    password2 = forms.CharField(widget=forms.PasswordInput(),
                                label="Reenter new Password", min_length=8)
    TACcheckbox = forms.BooleanField(label="I agree", required=True)

    def clean(self):
        cleaned_data = super(SignupForm, self).clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 != password2:
            self._errors['password2'] = u'Your passwords did not match'
            raise forms.ValidationError("Your passwords did not match")
        return cleaned_data


class LinkAccountForm(forms.Form):
    utility_provider = forms.ModelChoiceField(
        queryset=UtilityProvider.objects.all(),
        label="Choose your Utility Company", empty_label=None)
    utility_account_number = forms.CharField(max_length=40,
                                             label="Your Utility Account Number",
                                             required=False)
    street1 = forms.CharField(max_length=200, label="Address Line 1",
                              required=False)
    street2 = forms.CharField(max_length=200, label="Address Line 2",
                              required=False)
    city = forms.CharField(max_length=80, label="City",
                              required=False)
    state = forms.ModelChoiceField(queryset=State.objects.all(),
                                   label="State/Province/Region",
                                   empty_label=None,
                                   required=False)
    zip = forms.CharField(max_length=10, label="ZIP/Postal Code",
                              required=False)
    username = forms.CharField(max_length=64, label="Username", required=False)
    password1 = forms.CharField(widget=forms.PasswordInput(render_value=True),
                                max_length=64, label="Password",
                                required=False)
    password2 = forms.CharField(widget=forms.PasswordInput(render_value=True),
                                max_length=64,
                                label="Repeat your password", required=False)

    def clean(self):
        cleaned_data = super(LinkAccountForm, self).clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 != password2:
            raise forms.ValidationError("Your passwords did not match")
            #Check if form contains data at all
        # Address is optional, but if street1, street2, city or zip
        # are filled out, the complete address has to be filled out
        if cleaned_data.get('street1') or cleaned_data.get(
                'street2') or cleaned_data.get('city') or cleaned_data.get(
                'zip'):
            address = True
            if not (cleaned_data.get('street1') and cleaned_data.get(
                    'city') and cleaned_data.get('zip') and cleaned_data.get(
                    'state')):
                raise forms.ValidationError(
                    "The Address you provided was incomplete.")
        else:
            address = False
        # User has to either enter a Username, An Account Number or an
        # Address in order for us to identify him
        if not address and not cleaned_data.get(
                'utility_account_number') and not cleaned_data.get(
                'username'):
            raise forms.ValidationError(
                "You must provide an account number, a service address or your\
                 online login information")
        return cleaned_data


class LinkWebAccountForm(forms.Form):
    state = forms.ModelChoiceField(
        queryset=State.objects.filter(brokerage_possible=True),
        label="State:",
        required=False, empty_label=None
    )
    utility_provider = forms.ModelChoiceField(
        queryset=UtilityProvider.objects.select_related('state').all(),
        label="Utility:",
        empty_label=None)
    username = forms.CharField(max_length=500, label="Username", required=True)
    password1 = forms.CharField(widget=forms.PasswordInput(render_value=True),
                                max_length=500, label="Password",
                                required=False)
    password2 = forms.CharField(widget=forms.PasswordInput(render_value=True),
                                max_length=500,
                                label="Repeat password", required=False)

    def clean(self):
        cleaned_data = super(LinkWebAccountForm, self).clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 != password2:
            raise forms.ValidationError("Your passwords did not match")
        return cleaned_data


class LinkUtilAccountForm(forms.Form):
    utility_provider = forms.ModelChoiceField(
        queryset=UtilityProvider.objects.all(),
        label="Choose your Utility Company", empty_label=None)
    utility_account_number = forms.CharField(max_length=40,
                                             label="Your Utility Account Number",
                                             required=False)
    street1 = forms.CharField(max_length=200, label="Address Line 1",
                              required=False)
    street2 = forms.CharField(max_length=200, label="Address Line 2",
                              required=False)
    city = forms.CharField(max_length=80, label="City",
                              required=False)
    state = forms.ModelChoiceField(queryset=State.objects.all(),
                                   label="State/Province/Region",
                                   empty_label=None,
                                   required=False)
    zip = forms.CharField(max_length=10, label="ZIP/Postal Code",
                              required=False)

    def clean(self):
        cleaned_data = super(LinkUtilAccountForm, self).clean()
            #Check if form contains data at all
        # Address is optional, but if street1, street2, city or zip
        # are filled out, the complete address has to be filled out
        if cleaned_data.get('street1') or cleaned_data.get(
                'street2') or cleaned_data.get('city') or cleaned_data.get(
                'zip'):
            address = True
            if not (cleaned_data.get('street1') and cleaned_data.get(
                    'city') and cleaned_data.get('zip') and cleaned_data.get(
                    'state')):
                raise forms.ValidationError(
                    "The Address you provided was incomplete.")
        else:
            address = False
        # User has to either enter a Username, An Account Number or an
        # Address in order for us to identify him
        if not address and not cleaned_data.get(
                'utility_account_number'):
            raise forms.ValidationError(
                "You must provide an account number or"
                " a service address or your")
        return cleaned_data