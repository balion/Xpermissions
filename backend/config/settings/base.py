import os
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

AUTH_USER_MODEL = 'accounts.User'

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'djangosaml2',
]

LOCAL_APPS = [
    'apps.core.apps.CoreConfig',
    'apps.accounts.apps.AccountsConfig',
    'apps.roles.apps.RolesConfig',
    'apps.audit.apps.AuditConfig',
    'apps.projects.apps.ProjectsConfig',
    'apps.email_templates.apps.EmailTemplatesConfig',
    'apps.approvals.apps.ApprovalsConfig',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'djangosaml2.middleware.SamlSessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.audit.middleware.AuditMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'apps.accounts.backends.SamlBackend',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='admin_Xpermisions'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/saml2/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=15, cast=int)
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)
    ),
    'ROTATE_REFRESH_TOKENS': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Admin Xpermisions API',
    'DESCRIPTION': 'REST API for Admin Xpermisions — users, roles, permissions, projects, audit.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'ENUM_NAME_OVERRIDES': {
        'UserStatusEnum': 'apps.accounts.models.STATUS_CHOICES',
        'ProjectStatusEnum': 'apps.projects.models.STATUS_CHOICES',
    },
}

EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.Xpermisions.EmailBackend'
)

# ---------------------------------------------------------------------------
# SAML 2.0
# ---------------------------------------------------------------------------
_SAML_DIR = str(BASE_DIR.parent / 'saml')

try:
    import saml2
    import saml2.saml

    SAML_CONFIG = {
        'xmlsec_binary': config('SAML_XMLSEC_BINARY', default='/usr/bin/xmlsec1'),
        'entityid': config('SAML_SP_ENTITY_ID', default='http://localhost:8000/saml2/metadata/'),
        'service': {
            'sp': {
                'name': 'Admin Xpermisions',
                'name_id_format': saml2.saml.NAMEID_FORMAT_EMAILADDRESS,
                'endpoints': {
                    'assertion_consumer_service': [
                        (
                            config('SAML_ACS_URL', default='http://localhost:8000/saml2/acs/'),
                            saml2.BINDING_HTTP_POST,
                        ),
                    ],
                    'single_logout_service': [
                        (
                            config('SAML_SLS_URL', default='http://localhost:8000/saml2/ls/'),
                            saml2.BINDING_HTTP_REDIRECT,
                        ),
                        (
                            config('SAML_SLS_POST_URL', default='http://localhost:8000/saml2/ls/post/'),
                            saml2.BINDING_HTTP_POST,
                        ),
                    ],
                },
                'allow_unsolicited': True,
                'authn_requests_signed': False,
                'want_assertions_signed': True,
                'want_response_signed': False,
            },
        },
        'metadata': {
            'local': [os.path.join(_SAML_DIR, 'idp_metadata.xml')],
        },
        # SP certificate and key — leave empty strings to skip signing/encryption
        'key_file': config('SAML_SP_KEY_FILE', default=os.path.join(_SAML_DIR, 'sp_key.pem')),
        'cert_file': config('SAML_SP_CERT_FILE', default=os.path.join(_SAML_DIR, 'sp_cert.pem')),
        'encryption_keypairs': [
            {
                'key_file': config('SAML_SP_KEY_FILE', default=os.path.join(_SAML_DIR, 'sp_key.pem')),
                'cert_file': config('SAML_SP_CERT_FILE', default=os.path.join(_SAML_DIR, 'sp_cert.pem')),
            }
        ],
    }
except ImportError:
    SAML_CONFIG = {}

# Map SAML attributes to User model fields.
# Adjust attribute names to match your IdP (Azure AD, Keycloak, Okta, …).
SAML_ATTRIBUTE_MAPPING = {
    'mail': ('email',),
    'givenName': ('first_name',),
    'sn': ('last_name',),
    'cn': ('username',),
}

SAML_CREATE_UNKNOWN_USER = True

# ---------------------------------------------------------------------------
# LDAP (used only for the user-import UI, not for authentication)
# ---------------------------------------------------------------------------
LDAP_SERVER_URI = config('LDAP_SERVER_URI', default='ldap://localhost')
LDAP_BIND_DN = config('LDAP_BIND_DN', default='')
LDAP_BIND_PASSWORD = config('LDAP_BIND_PASSWORD', default='')
LDAP_SEARCH_BASE = config('LDAP_SEARCH_BASE', default='dc=example,dc=com')
LDAP_ATTR_EMAIL = config('LDAP_ATTR_EMAIL', default='mail')
LDAP_ATTR_FIRST_NAME = config('LDAP_ATTR_FIRST_NAME', default='givenName')
LDAP_ATTR_LAST_NAME = config('LDAP_ATTR_LAST_NAME', default='sn')
LDAP_ATTR_USERNAME = config('LDAP_ATTR_USERNAME', default='sAMAccountName')
