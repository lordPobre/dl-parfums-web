"""Ajustes para el CI y las pruebas. Parte de core/settings.py y cambia solo lo necesario.

Uso: DJANGO_SETTINGS_MODULE=core.settings_ci python manage.py test
"""
from .settings import *  # noqa: F401,F403
from .settings import DATABASES, STORAGES

# El Postgres del CI corre sin SSL (producción sigue con sslmode=require).
if DATABASES["default"]["ENGINE"].endswith("postgresql"):
    DATABASES["default"]["OPTIONS"] = {}

# Las pruebas no suben nada a Cloudinary: las imágenes viven en memoria.
STORAGES = {**STORAGES, "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}}

# Contraseñas rápidas de hashear (solo afecta a usuarios creados en pruebas).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
