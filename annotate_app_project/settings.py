"""
Django settings for annotate_app_project project.

Generated by 'django-admin startproject' using Django 5.1.7.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


CSRF_TRUSTED_ORIGINS = [
    "https://proteintinder2.bionetic.org",
    "http://proteintinder2.bionetic.org",  # add this just in case
    "https://proteintinder.bionetic.org",
    "http://proteintinder.bionetic.org",  # add this just in case
]

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # Only if using proxy

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-fallback-key-for-non-docker')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True' # Check for 'True' string

ALLOWED_HOSTS = ['proteintinder2.bionetic.org', 'www.proteintinder2.bionetic.org','proteintinder.bionetic.org', 'www.proteintinder.bionetic.org']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'annotations_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'annotate_app_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Add this line to look for templates in BASE_DIR/templates
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True, # Keep this True to also find templates in app directories
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

WSGI_APPLICATION = 'annotate_app_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.environ.get('DB_NAME', BASE_DIR / 'db.sqlite3'), # Default to SQLite if vars not set
        'USER': os.environ.get('DB_USER'), # No default needed for SQLite
        'PASSWORD': os.environ.get('DB_PASSWORD'), # No default needed for SQLite
        'HOST': os.environ.get('DB_HOST'), # No default needed for SQLite
        'PORT': os.environ.get('DB_PORT'), # No default needed for SQLite
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
         } if os.environ.get('DB_ENGINE') == 'django.db.backends.mysql' else {}, # Only set for MySQL
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

# Static files (CSS, JavaScript, Images)
# URL to access static files
STATIC_URL = '/static/'

# Directory where collectstatic will place all static files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Directories to find static files during development
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]


# === ADD MEDIA FILES CONFIGURATION ===
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media' # Corresponds to /app/media/ in the container

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

USE_X_FORWARDED_HOST = True
