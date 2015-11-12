# Django settings for xbill project.

from os.path import dirname, realpath
SITE_ROOT = dirname(dirname(realpath(__file__)))
HOST_ADDRESS = "http://localhost:8000"

DEBUG = True
COMPRESS_ENABLED = False
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'
        'NAME': 'xbill', # Or path to database file if using sqlite3.
        # The following settings are not used with sqlite3:
        'USER': 'dev',
        'PASSWORD': 'dev',
        'HOST': '', # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '', # Set to empty string for default.
    }
}

# Hosts/domain names that are valid for this site; required if DEBUG is False
# See https://docs.djangoproject.com/en/1.5/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ['localhost','xbill-localdev']

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'America/New_York'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = 'static'

# URL prefix for static files.
# Example: "http://example.com/static/", "http://static.example.com/"
STATIC_URL = '/static/'

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    #   'django.contrib.staticfiles.finders.DefaultStorageFinder',
    'compressor.finders.CompressorFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'oe%%z9^3er5t-n-mjvl=bkf)lvx*p9mg=ko6y559r^0pw_)b5e'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django_pdb.middleware.PdbMiddleware',  # DEBUG don't add in production
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'xbill.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'wsgi.wsgi.application'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    SITE_ROOT+'/shared/templates/',
)

MESSAGE_STORAGE = 'django.contrib.messages.storage.cookie.CookieStorage'
LOGIN_URL = '/login'
LOGOUT_URL = '/logout'
AUTH_USER_MODEL = 'intro.User'
SESSION_COOKIE_NAME = 'xbillsessionid'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.webdesign',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'widget_tweaks',  # Allows adding classes/attributes to form widgets
    'south',  # Database Migration Tool
    'compressor',  # django-compressor: Compresses CSS/JS and prevents stale browser cache
    'django_pdb',  # DEBUG don't add in production
    'rest_framework',

    'intro',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'intro.processors.sort_messages',

    #'social.apps.django_app.context_processors.backends',
    #'social.apps.django_app.context_processors.login_redirect',
)

SOUTH_TESTS_MIGRATE = False

#AUTHENTICATION_BACKENDS = (
    #'social.backends.open_id.OpenIdAuth',
    #'social.backends.google.GoogleOpenId',
    #'social.backends.google.GoogleOAuth2',
    #'social.backends.google.GoogleOAuth',
    #'social.backends.twitter.TwitterOAuth',
    #'social.backends.yahoo.YahooOpenId',
    #'django.contrib.auth.backends.ModelBackend',
#)

LOGGING_DIR_PATH = "/tmp/"
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format' : "[%(asctime)s] %(levelname)s [%(pathname)s:%(lineno)s] %(message)s",
            'datefmt' : "%d/%b/%Y %H:%M:%S"
        },
    },
    'handlers': {
        'null': {
            'level':'DEBUG',
            'class':'django.utils.log.NullHandler',
        },
        'logfile': {
            'level':'DEBUG',
            'class':'logging.handlers.RotatingFileHandler',
            'filename': LOGGING_DIR_PATH + "xbill.log",
            'maxBytes': 1000000,
            'backupCount': 2,
            'formatter': 'standard',
        },
        'django-logfile': {
            'level':'DEBUG',
            'class':'logging.handlers.RotatingFileHandler',
            'filename': LOGGING_DIR_PATH + "xbill_django.log",
            'maxBytes': 1000000,
            'backupCount': 2,
            'formatter': 'standard',
        },
        'request-logfile': {
            'level':'DEBUG',
            'class':'logging.handlers.RotatingFileHandler',
            'filename': LOGGING_DIR_PATH + "xbill_request.log",
            'maxBytes': 1000000,
            'backupCount': 2,
            'formatter': 'standard',
        },
        'db-logfile': {
            'level':'DEBUG',
            'class':'logging.handlers.RotatingFileHandler',
            'filename': LOGGING_DIR_PATH + "xbill_db.log",
            'maxBytes': 1000000,
            'backupCount': 2,
            'formatter': 'standard',
        },
        'etl-logfile': {
            'level':'DEBUG',
            'class':'logging.handlers.RotatingFileHandler',
            'filename': LOGGING_DIR_PATH + "xbill_etl.log",
            'maxBytes': 1000000,
            'backupCount': 2,
            'formatter': 'standard',
        },
        'console':{
            'level':'DEBUG',
            'class':'logging.StreamHandler',
            'formatter': 'standard'
        },
    },
    'loggers': {
        'django': {
            'handlers':['django-logfile'],
            'propagate': True,
            'level': 'DEBUG',
        },
        'django.db.backends': {
            'handlers': ['db-logfile'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['request-logfile'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'xbill': {
            'handlers': ['logfile', 'console'],
            'level': 'DEBUG',
        },
        'xbill-etl': {
            'handlers': ['etl-logfile'],
            'level': 'DEBUG',
        },
    }
}

USER_MUST_VERIFY_EMAIL = True
CREATE_TOKEN = True
SEND_EMAIL = True
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = 'jwatson@skylineinnovations.com'
EMAIL_HOST_PASSWORD = 'gkjtiNnpv85HhWjKue8w'
EMAIL_USE_TLS = True
EMAILER = {
    'smtp_host' : 'smtp.gmail.com',
    'smtp_port' : 587,
    'imap_host' : 'imap.gmail.com',
    'imap_port' : 993,
    'originator' : 'jwatson@skylineinnovations.com',
    'from' : '"Jules Watson" <jwatson@skylineinnovations.com>',
    'bcc_list' : [],
    'password' : 'password',
    'delivery_confirmation_recipient' : 'jwatson@skylineinnovations.com',
    'email_token_prefix' : 'skylineemail#',
}
ENCRYPTION = {
    'salt' : b'\xb8-U\x84\x1f\xdbs\x90\\f\x83\x16\x90H\x96\x17\xcf|sX\x9f\xf8\x90J\xc8\xf2\xf9-\x94\xe9t1',
    'password' : b'\x87\xdd\xf1\xde\x84_\xdbqT\xf0\xb7\xf2\xe7\xda\xdd\x8b0\x16-\x88XG\xa0\x03p\x06J\xa2*\xa6\x8eL',
    'block_size' : 32,
    'padding' : '\v',
}

#COMPRESS_OUTPUT_DIR="CACHE/"
COMPRESS_CSS_FILTERS = [
    'compressor.filters.cssmin.CSSMinFilter',
    'compressor.filters.css_default.CssAbsoluteFilter'
]
COMPRESS_JS_FILTERS = [
    'compressor.filters.jsmin.JSMinFilter'
]

###########################################
#
#     ETL CONFIGURATION
XBILL_ETL_DIR = '/tmp/'
XBILL_ETL_ADD_ACCOUNT_DIR = 'add_account/'
XBILL_ETL_ACCOUNTS_DIR = 'accounts/'

###########################################
#
#     REST CONFIGURATION
REST_FRAMEWORK = {
    # Use hyperlinked styles by default.
    # Only used if the `serializer_class` attribute is not set on a view.
    'DEFAULT_MODEL_SERIALIZER_CLASS':
        'rest_framework.serializers.HyperlinkedModelSerializer',

    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny'
    ]
}

###########################################
#
#     S3 CONFIGURATION
S3_ACCESS_KEY = 'AKIAIBQBJBWZPQIHPQXA'
S3_SECRET_KEY = '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'


###########################################
#
#     AMQP CONFIGURATION
xbill_account_publisher = {'publish_to': ('altitude', 'AccountHandler')}
xbill_individual_publisher = {'publish_to': ('altitude', 'IndividualHandler')}
make_scrape_request_publisher = {'publish_to': ('acquisitor', 'scrape_bills'),
                                 'respond_to': ('acquisitor',
                                                'scrape_bills_callback')}
utility_provider_publisher = {'publish_to': ('reebill', 'process_utility')}
