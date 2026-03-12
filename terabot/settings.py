import os

SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-production')
DEBUG = False
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'chatbot',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

ROOT_URLCONF = 'terabot.urls'
WSGI_APPLICATION = 'terabot.wsgi.application'

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db.sqlite3'),
    }
}

# Gmail SMTP
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_USE_SSL       = False
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = EMAIL_HOST_USER

# TeraBOT
GROQ_API_KEY             = os.environ.get('GROQ_API_KEY', '')
CHATBOT_ALLOWED_ORIGIN   = os.environ.get('CHATBOT_ALLOWED_ORIGIN', '*')
LEAD_NOTIFICATION_EMAILS = os.environ.get('LEAD_EMAILS', 'yogesh@teralumen.com').split(',')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
}