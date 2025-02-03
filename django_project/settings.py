from pathlib import Path
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
import os

SECRET_KEY = os.environ.get("SECRET_KEY")


DEBUG = bool(os.environ.get("DEBUG", default=0))


print(f"DEBUG setting is: {DEBUG}")


ALLOWED_HOSTS = [
    "localhost",
    "0.0.0.0",
    "127.0.0.1",
    "wdc.smartflow.pw",
]


# Application definition
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    # "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party
    "allauth",
    "allauth.account",
    "crispy_forms",
     'django_celery_results',
     'django_celery_beat',
      'django_htmx',
      "crispy_tailwind",
      'dbbackup',
    # Local
    "accounts",
    "pages",
    "document",
    "backup_manager"

]

if DEBUG:
    INSTALLED_APPS.append("debug_toolbar")
    INSTALLED_APPS.append("django_browser_reload")

CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"

CRISPY_TEMPLATE_PACK = "tailwind"

# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [

    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # WhiteNoise
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", 
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # django-allauth
    "django_htmx.middleware.HtmxMiddleware",  # django-htmx
    "document.middleware.msgMiddleware", # toast
]

if DEBUG:
    MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")
    MIDDLEWARE.append("django_browser_reload.middleware.BrowserReloadMiddleware")

# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "django_project.urls"

# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "django_project.wsgi.application"

# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "document.context_processors.user_bu_groups",  # Add BU groups to context
                "document.context_processors.pending_documents_count", # Add Pending count   to context
            ],
        },
    },
]


DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600
    )
}

# Password validation
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
# AUTH_PASSWORD_VALIDATORS = [
#     {
#         "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
#     },
#     {
#         "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
#     },
#     {
#         "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
#     },
#     {
#         "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
#     },
# ]

AUTH_PASSWORD_VALIDATORS = []


# Internationalization
# https://docs.djangoproject.com/en/dev/topics/i18n/
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"

# https://docs.djangoproject.com/en/dev/ref/settings/#time-zone
TIME_ZONE = 'Asia/Bangkok'

# https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-USE_I18N
USE_I18N = True

# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True

# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [BASE_DIR / 'locale']

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = BASE_DIR / "staticfiles"

# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"

# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [BASE_DIR / "static"]

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: True,
}

# https://whitenoise.readthedocs.io/en/latest/django.html
# STORAGES = {
#     "default": {
#         "BACKEND": "django.core.files.storage.FileSystemStorage",
#     },
#     "staticfiles": {
#         "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
#     },
# }
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Maximum request body size (8MB to allow form validation to handle image sizes)
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024  # 8 MB

# Maximum size for a single field value (handled by form validation)
# DATA_UPLOAD_MAX_MEMORY_SIZE_PER_FIELD = 2 * 1024 * 1024  # 2MB

# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# django-crispy-forms
# https://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs



DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')
USE_SES_V2 = True

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
if EMAIL_BACKEND == "ses":
    EMAIL_BACKEND = 'django_ses.SESBackend'
    AWS_SES_REGION_NAME = os.environ.get('AWS_SES_REGION_NAME')
    AWS_SES_REGION_ENDPOINT = os.environ.get('AWS_SES_REGION_ENDPOINT')
    AWS_SES_ACCESS_KEY_ID = os.environ.get('AWS_SES_ACCESS_KEY_ID')
    AWS_SES_SECRET_ACCESS_KEY = os.environ.get('AWS_SES_SECRET_ACCESS_KEY')
    


# django-debug-toolbar
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html
# https://docs.djangoproject.com/en/dev/ref/settings/#internal-ips
INTERNAL_IPS = ["127.0.0.1"]

# https://docs.djangoproject.com/en/dev/topics/auth/customizing/#substituting-a-custom-user-model
AUTH_USER_MODEL = "accounts.CustomUser"

# django-allauth config
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1

# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "document_approval:documents_to_approve"

# https://django-allauth.readthedocs.io/en/latest/views.html#logout-account-logout
ACCOUNT_LOGOUT_REDIRECT_URL = "home"

# https://django-allauth.readthedocs.io/en/latest/installation.html?highlight=backends
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = False
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
# ACCOUNT_SIGNUP_FORM_CLASS = "accounts.forms.CustomSignupForm"


ACCOUNT_FORMS = {'signup': 'accounts.forms.CustomSignupForm'}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


CSRF_COOKIE_SECURE = True  # Set to True if using HTTPS
CSRF_COOKIE_DOMAIN = '.wdc.smartflow.pw'  # Include your domain here
SESSION_COOKIE_SECURE = True  # Set to True if using HTTPS

CSRF_TRUSTED_ORIGINS = ['https://www.wdc.smartflow.pw', 'https://wdc.smartflow.pw']

# Celery Settings
CELERY_TIMEZONE = os.environ.get('CELERY_TIMEZONE', 'Asia/Bangkok')


CELERY_BROKER_URL = f"redis://:{os.getenv('REDIS_PASSWORD')}@redis:6379/0"

CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Celery Beat Settings
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Django DB Backup settings
DBBACKUP_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
DBBACKUP_STORAGE_OPTIONS = {
    'access_key': os.environ.get('AWS_ACCESS_KEY_ID'),
    'secret_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
    'bucket_name': os.environ.get('AWS_STORAGE_BUCKET_NAME'),
    'endpoint_url': os.environ.get('AWS_S3_ENDPOINT_URL'),
    'default_acl': 'private',
    'location': 'backupdb'  
}
DBBACKUP_CLEANUP_KEEP = 3  # Keep last 3 backups
DBBACKUP_FILENAME_TEMPLATE = '{datetime}.{extension}'

# Enable console output for dbbackup
DBBACKUP_CONNECTORS = {
    'default': {
        'CONNECTOR': 'dbbackup.db.postgresql.PgDumpConnector',
        'DUMP_CMD': 'pg_dump',
        'RESTORE_CMD': 'psql',
    }
}

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL')
AWS_QUERYSTRING_AUTH = True  # Enable signed URLs
AWS_DEFAULT_ACL = 'private'  # Ensure files are private
AWS_S3_FILE_OVERWRITE = False  # Avoid overwriting files
AWS_QUERYSTRING_EXPIRE = 30

DEFAULT_FILE_STORAGE = 'django_project.storage_backends.CustomS3Storage'
