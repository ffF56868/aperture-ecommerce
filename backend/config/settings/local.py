"""Local development settings."""

from importlib.util import find_spec

from .base import *  # noqa: F401,F403

DEBUG = True

# The Django admin is served through the local Nginx frontend on port 3000.
CSRF_TRUSTED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

if find_spec("debug_toolbar") is not None:
    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405

INTERNAL_IPS = ["127.0.0.1"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
