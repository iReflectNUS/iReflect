"""
Django settings for pigeonhole project.

Generated by 'django-admin startproject' using Django 4.0.2.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.0/ref/settings/
"""

import os
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(int(os.getenv("DEBUG", 0)))

# CORS is disabled in debug mode
CORS_ALLOW_ALL_ORIGINS = DEBUG

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS").split(" ")

CSRF_TRUSTED_ORIGINS = [
    f"http{'' if DEBUG else 's'}://{host}" for host in ALLOWED_HOSTS
]

# Ensure CSRF cookies are only sent on same-site requests
CSRF_COOKIE_SAMESITE = 'Strict'

# Prevent JavaScript from accessing the CSRF cookie
CSRF_COOKIE_HTTPONLY = True

# Only send the CSRF cookie over HTTPS (useful in production)
CSRF_COOKIE_SECURE = True

SITE_ID = 1


# Application definition

INSTALLED_APPS = [
    "jazzmin",
    "django_json_widget",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.flatpages",
    "corsheaders",
    "pigeonhole",
    "content_delivery_service",
    "users",
    "authentication",
    "courses",
    "forms",
    "feedback",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "pigeonhole.middleware.timezone.TimezoneMiddleware",
]

ROOT_URLCONF = "pigeonhole.urls"

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
                "pigeonhole.module.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "pigeonhole.wsgi.application"

## Django admin theming
## https://django-jazzmin.readthedocs.io/index.html

JAZZMIN_SETTINGS = {
    "site_title": "iReflect",
    "site_header": "iReflect Admin",
    "site_brand": "iReflect Admin",
    "welcome_sign": "Welcome to iReflect Administration",
    "copyright": "iReflect",
    ## "site_logo": "treeckle-min.png",  ## TODO: change
    "site_icon": "favicon-32x32.png",  ## TODO: change
    "hide_apps": ["auth"],
    "icons": {
        "authentication.googleauthentication": "fab fa-google",
        "authentication.facebookauthentication": "fab fa-facebook",
        "authentication.passwordauthentication": "fas fa-key",
        "content_delivery_service.image": "fas fa-image",
        "users.user": "fas fa-users",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": False,
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": True,
    "sidebar_fixed": False,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": True,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "darkly",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-outline-info",
        "warning": "btn-outline-warning",
        "danger": "btn-outline-danger",
        "success": "btn-outline-success",
    },
}

## REST framework and JWT
## https://www.django-rest-framework.org/
## https://django-rest-framework-simplejwt.readthedocs.io/en/latest/
## https://pypi.org/project/djangorestframework-camel-case/

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTTokenUserAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": (
        "djangorestframework_camel_case.render.CamelCaseJSONRenderer",
        "djangorestframework_camel_case.render.CamelCaseBrowsableAPIRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
    ),
    "JSON_UNDERSCOREIZE": {
        "no_underscore_before_number": True,
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=14) if DEBUG else timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
}

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": os.getenv("SQL_ENGINE", "django.db.backends.postgresql"),
        "NAME": os.getenv("SQL_DATABASE", BASE_DIR / "db.postgresql"),
        "USER": os.getenv("SQL_USER", "user"),
        "PASSWORD": os.getenv("SQL_PASSWORD", "password"),
        "HOST": os.getenv("SQL_HOST", "localhost"),
        "PORT": os.getenv("SQL_PORT", "5432"),
    }
}

## Password hashers
## https://docs.djangoproject.com/en/4.0/topics/auth/passwords/

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]


# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

MIN_PASSWORD_LENGTH = 8

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": MIN_PASSWORD_LENGTH,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

PASSWORD_RESET_TIMEOUT = 1800   # 30 minutes

# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

## To serve django admin css when in production
STATIC_URL = "/api/static/"
STATIC_ROOT = "static"

# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

## Logging

## default logging config can be found here: https://docs.djangoproject.com/en/4.0/ref/logging/#default-logging-definition-1

## logging extension
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "formatters": {
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[dev server] {asctime}.{msecs:03.0f} {message}",
            "style": "{",
            "datefmt": "%d/%m/%Y %H:%M:%S",
        },
        "default": {
            "()": "colorlog.ColoredFormatter",
            "format": "{log_color}[{levelname}] {asctime}.{msecs:03.0f} {pathname} (line {lineno}) {message}",
            "style": "{",
            "datefmt": "%d/%m/%Y %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "mail_admins"],
            "level": "INFO",
        },
        "django.server": {
            "handlers": ["django.server"],
            "level": "INFO",
            "propagate": False,
        },
        "main": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "DEBUG" if DEBUG else "INFO"),
        },
    },
}
