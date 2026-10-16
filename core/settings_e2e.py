"""Ajustes para las pruebas en navegador (catalogo/tests_e2e.py). Parte de settings_ci.

Uso: E2E=1 DJANGO_SETTINGS_MODULE=core.settings_e2e python manage.py test catalogo.tests_e2e
"""
from .settings_ci import *  # noqa: F401,F403
from .settings_ci import STORAGES

# El servidor de pruebas sirve los estáticos desde las carpetas del proyecto, sin manifiesto de hashes.
STORAGES = {**STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}

# El servidor de pruebas es http: las cookies Secure no se guardarían y el pedido fallaría por CSRF.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
