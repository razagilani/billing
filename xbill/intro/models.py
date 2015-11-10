from django.db import models
from django.db import IntegrityError
from datetime import date
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, \
    PermissionsMixin
from xbill import settings
from utils.Encryptor import Encryptor
import random
import string
from django.utils import timezone
import uuid

def make_guid():
    return str(uuid.uuid4())

class UtilityService(models.Model):
    class Meta:
        verbose_name = "Utility Service"
        verbose_name_plural = "Utility Services"

    name = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return unicode(self.name)


class Content(models.Model):
    class Meta:
        verbose_name = "Content"
        verbose_name_plural = "Content"

    name = models.CharField(max_length=50)
    short_desc = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    version = models.PositiveSmallIntegerField()
    lang = models.CharField(max_length=5, default='en')
    modified_by = models.ForeignKey('User', null=True, blank=True)

    @classmethod
    def get_last_version(cls, name):
        """
        Shortcut to get the latest version of the content with name=name
        """
        try:
            return cls.objects.filter(name__iexact=name).order_by('-version')[0]
        except IndexError:
            raise cls.DoesNotExist

    @classmethod
    def get_last_tou_version_number(cls):
        """
        Returns the Integer of the last version number of the TOU content
        """
        try:
            return cls.get_last_version('TOU').version
        except cls.DoesNotExist:
            # TOU content not found
            return 0

    def __unicode__(self):
        return "%s Version %s" % (self.name, self.version)


class State(models.Model):
    class Meta:
        verbose_name = "State"
        verbose_name_plural = "States"

    abbr = models.CharField(max_length=100, null=True)
    name = models.CharField(max_length=300)
    brokerage_possible = models.BooleanField(default=False)

    def __unicode__(self):
        if not self.name:
            return unicode(self.abbr)
        return unicode(self.name)


class Address(models.Model):
    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"

    street1 = models.CharField(max_length=400, null=True, blank=True)
    street2 = models.CharField(max_length=400, null=True, blank=True)
    city = models.CharField(max_length=80, null=True, blank=True)
    state = models.ForeignKey(State)
    zip = models.CharField(max_length=20, null=True, blank=True)

    def __unicode__(self):
        state = self.state.__unicode__()
        return u' '.join(filter(None, (self.street1, self.street2, self.city,
                                       state, self.zip)))


class Account(models.Model):
    class Meta:
        ordering = ['-id']
        verbose_name = "Account"
        verbose_name_plural = "Accounts"

    address = models.ForeignKey(Address, null=True, blank=True)
    name = models.CharField(max_length=300, null=True, blank=True)
    guid = models.CharField(max_length=36, null=True, blank=True, unique=True, default=make_guid)
    # A unique token that can be use to represent this Account in an URL
    # This is currently only used to
    token = models.CharField(max_length=60, null=True, blank=True, unique=True)
    # We can not use auto_add_now for the following, since we want to be able
    # to set the field to null in some circumstances
    tou_signed = models.DateTimeField(default=timezone.now, null=True,
                                      blank=True)
    tou_version_signed = models.PositiveSmallIntegerField(null=True, blank=True)
    tou_signed_http_headers = models.TextField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    modified = models.DateTimeField(auto_now=True, null=True, blank=True)

    # We want to update tou_version_signed whenever tou_signed changes
    # To prevent having to make another DB call we will store the original value
    # in the following variable and compare against it
    # http://stackoverflow.com/questions/1355150/
    #   django-when-saving-how-can-you-check-if-a-field-has-changed
    __orignial_tou_signed = None

    def __init__(self, *args, **kwargs):
        super(Account, self).__init__(*args, **kwargs)
        self.__orignial_tou_signed = self.tou_signed

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        # Check if the __orignial_tou_signed was updated
        # We also need to update tou_version_signed when tou_signed was
        # created with its default
        if (self.__orignial_tou_signed != self.tou_signed) or \
            (self.tou_signed is not None and self.tou_version_signed is None):
                self.tou_version_signed = Content.get_last_tou_version_number()
        super(Account, self).save(force_insert, force_update, *args, **kwargs)
        self.__orignial_tou_signed = self.tou_signed

    def __unicode__(self):
        if self.name:
            return self.name
        if self.address:
            addr = self.address.__unicode__()
            if addr:
                return addr
        if self.guid:
            return unicode(self.guid)
        if self.address:
            return unicode(self.address)
        if self.token:
            return u"Token: " + unicode(self.token)
        return 'Id: ' + unicode(self.id)

    def set_tou_http_headers_from_request(self, request):
        if not request.user.is_anonymous():
            name = request.user.get_full_name()
            email = request.user.email_address
            account = request.user.account if request.user.account else ""
        else:
            name, email, account = ('', '', '')
        self.tou_signed_http_headers = "Date/Time: %s\n" \
                                       "User: %s %s (Account: %s)\n" \
                                       "Client: %s %s %s\n" \
                                       "Accepts: %s %s %s\n" \
                                       "Requested: %s %s: %s (%s) %s\n" \
                                       "Cookies: %s" % (
                                           timezone.now().strftime(
                                               '%Y-%m-%dT%H:%M:%S%z'),
                                           name,
                                           email,
                                           account,
                                           request.META.get('REMOTE_ADDR'),
                                           request.META.get('REMOTE_HOST'),
                                           request.META.get('HTTP_USER_AGENT'),
                                           request.META.get('HTTP_ACCEPT'),
                                           request.META.get(
                                               'HTTP_ACCEPT_LANGUAGE'),
                                           request.META.get(
                                               'HTTP_ACCEPT_ENCODING'),
                                           request.META.get('SERVER_PROTOCOL'),
                                           request.META.get('HTTP_CONNECTION'),
                                           request.META.get('HTTP_HOST'),
                                           request.META.get('SERVER_NAME'),
                                           request.META.get('PATH_INFO'),
                                           request.META.get('HTTP_COOKIE')
                                       )


class CustomUserManager(BaseUserManager):
    def create_user(self, account, email_address, password):
        if not email_address:
            raise ValueError('Users must have an email address')

        user = self.model(account=account,
                          email_address=self.normalize_email(email_address))

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email_address, password):
        if not email_address:
            raise ValueError('Users must have an email address')

        user = self.model(email_address=self.normalize_email(email_address))
        user.is_admin = True
        user.is_superuser = True
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    USERNAME_FIELD = 'email_address'

    # Class constants and choices for self.user_state
    ACTIVE = 50
    INACTIVE = 30
    GHOST = 10
    MASTER = 100
    USER_STATE_CHOICES = (
        (GHOST, "Ghost"),
        (INACTIVE, "Inactive"),
        (ACTIVE, "Active"),
        (MASTER, "Master")
    )

    email_address = models.CharField(max_length=500, unique=True, db_index=True)
    email_address_verified = models.BooleanField(default=False)
    identifier = models.CharField(max_length=500, blank=True,
                                  null=True)  # OpenId identifier
    user_state = models.PositiveSmallIntegerField(default=ACTIVE,
                                                  choices=USER_STATE_CHOICES,
                                                  blank=False)
    account = models.ForeignKey(Account, null=True, blank=True)
    first_name = models.CharField(max_length=40, null=True, blank=True)
    last_name = models.CharField(max_length=40, null=True, blank=True)
    guid = models.CharField(max_length=36, null=True, blank=True, unique=True, default=make_guid)
    is_admin = models.BooleanField(default=False)  # needed for Django Admin
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    modified = models.DateTimeField(auto_now=True, null=True, blank=True)
    # The following field indicates whether this account was created in Portal
    # or whether this User was created by the add_accounts importer
    imported = models.BooleanField(default=False)

    objects = CustomUserManager()

    def get_full_name(self):
        # Only print a space if there is a first name and a last name
        return " ".join(
            (name for name in (self.first_name, self.last_name) if name)
        )

    def get_short_name(self):
        if self.first_name:
            return self.first_name
        return ''

    def __unicode__(self):
        return unicode(self.email_address)

    @property
    def is_staff(self):
        return self.is_admin


class Token(models.Model):
    class Meta:
        verbose_name = "Token"
        verbose_name_plural = "Tokens"

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    token = models.CharField(max_length=60, unique=True)
    purpose = models.CharField(max_length=50)
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField()

    @classmethod
    def create_token(cls, user, purpose, years=0, months=0, days=0, weeks=0,
                     hours=0, minutes=0, seconds=0, microseconds=0):
        """
        This method creates a random unique token.
        """
        token = ''.join(
            random.choice(string.ascii_letters + string.digits) for __ in
            xrange(60))
        token_saved = False
        t = None
        while not token_saved:
            try:
                token_expires = date.today() + \
                    relativedelta(years=years, months=months, weeks=weeks,
                                  days=days, hours=hours, minutes=minutes,
                                  seconds=seconds, microseconds=microseconds)
                t = cls(user=user, token=token, purpose=purpose,
                        expires=token_expires)
                t.save()
                token_saved = True
            except IntegrityError:
                # This specific token already exists in the database.
                # Create another one
                pass
        return t

    def __unicode__(self):
        return "%s token for %s: (%s)" % (self.purpose, self.user, self.token)


class UtilityProvider(models.Model):
    class Meta:
        ordering = ['name']
        verbose_name = "Utility Provider"
        verbose_name_plural = "Utility Providers"

    UTILITY = 1
    SUPPLIER = 2
    UtilityProviderTypes = [
        (UTILITY, "Utility"),
        (SUPPLIER, "Supplier")
    ]

    name = models.CharField(max_length=500)
    display_name = models.CharField(max_length=500, null=True, blank=True)
    state = models.ForeignKey(State, null=True, blank=True)
    # TODO: remove registration rules
    registrationrule = models.PositiveSmallIntegerField(default=1)
    services = models.ManyToManyField(UtilityService, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    modified = models.DateTimeField(auto_now=True, null=True, blank=True)
    guid = models.CharField(max_length=36, null=True, blank=True, unique=True, default=make_guid)
    type = models.PositiveSmallIntegerField(default=UTILITY,
                                            choices=UtilityProviderTypes,
                                            blank=False)


    def get_display_name(self):
        if self.display_name:
            return unicode(self.display_name)
        return unicode(self.name)

    def supported_services(self):
        """
        Prints a list of names of services that this Utility provider is
        associated with
        """
        return ", ".join([service.name for service in self.services.all()])

    def __unicode__(self):
        return self.name


class UtilityWebsiteInformation(models.Model):
    class Meta:
        verbose_name = "Utility Website Credentials"
        verbose_name_plural = "Utility Website Credentials"

    utility_username = models.CharField(max_length=512)
    utility_password = models.CharField(max_length=512)
    utility_provider = models.ForeignKey(UtilityProvider)
    accounts = models.ManyToManyField(Account)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    modified = models.DateTimeField(auto_now=True, null=True, blank=True)
    comments = models.TextField(null=True, blank=True)

    @classmethod
    def create(cls, utility_username, utility_password, utility_provider,
               account):
        uwi = cls(utility_provider=utility_provider)
        uwi.set_password(utility_password)
        uwi.set_username(utility_username)
        uwi.save()
        uwi.accounts.add(account)
        return uwi

    def set_username(self, username):
        self.utility_username = Encryptor.encrypt(username)

    def set_password(self, password):
        self.utility_password = Encryptor.encrypt(password)

    def get_username(self):
        return Encryptor.decrypt(self.utility_username)

    def get_password(self):
        return Encryptor.decrypt(self.utility_password)

    def __unicode__(self):
        return '"%s" for %s ' % (
            unicode(self.get_username()), unicode(self.utility_provider))

    # Hack to view/edit the decrypted password via the admin page
    @property
    def utility_username_decrypted(self):
        return self.get_username()

    @property
    def utility_password_decrypted(self):
        return self.get_password()


