"""Real AA v5 apps and migrations; isolated SQLite and in-memory task transport."""

import django_redis
import fakeredis
from allianceauth.project_template.project_name.settings.base import *  # noqa: F403

# AA task statistics access Redis directly; give tests their own in-memory server.
_redis = fakeredis.FakeRedis()
_redis.info = lambda *args, **kwargs: {"redis_version": "7.0.0"}
django_redis.get_redis_connection = lambda *args, **kwargs: _redis

SECRET_KEY = "test-only-do-not-deploy"
SITE_URL = "http://testserver"
INSTALLED_APPS = INSTALLED_APPS + ["planetary_operations"]  # noqa: F405
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
LOGGING = {"version": 1, "disable_existing_loggers": False}
ROOT_URLCONF = "tests.urls"
STATICFILES_DIRS = []
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
BROKER_URL = "memory://"
ESI_SSO_CLIENT_ID = "test-client"
ESI_SSO_CLIENT_SECRET = "test-secret"
ESI_SSO_CALLBACK_URL = "http://testserver/sso/callback"
ESI_USER_CONTACT_EMAIL = "test@example.invalid"
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
USE_TZ = True
