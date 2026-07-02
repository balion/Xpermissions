
from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['*']

INTERNAL_IPS = ['127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
    }
}

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

# Print emails to the console in development — no SMTP server needed.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
