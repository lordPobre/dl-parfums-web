
import os
from pathlib import Path
import mimetypes
import dj_database_url
import cloudinary
from dotenv import load_dotenv

mimetypes.add_type("text/css", ".css", True)

BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)

SECRET_KEY = os.environ.get('SECRET_KEY')

# Vercel define VERCEL=1 en sus funciones. En tu PC no existe, así que se activa el modo local.
EN_PRODUCCION = os.environ.get('VERCEL') == '1'
DEBUG = os.environ.get('DEBUG', 'False' if EN_PRODUCCION else 'True') == 'True'

ALLOWED_HOSTS = ['instintoolfativo.cl', 'www.instintoolfativo.cl', '.vercel.app', 'localhost', '127.0.0.1']

# Dominio canónico: se usa en <link rel="canonical">, og:url, JSON-LD y la redirección de *.vercel.app
SITE_URL = 'https://www.instintoolfativo.cl'

INSTALLED_APPS = [
    'unfold',  # antes de django.contrib.admin
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'cloudinary_storage', 
    'cloudinary',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.postgres',   # búsqueda sin tildes y con tolerancia a errores
    'catalogo',
    'axes',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.dominio.DominioCanonicoMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'core.admin_2fa.Admin2FAMiddleware',  # A4: código del teléfono en el admin
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.security_headers.SecurityHeadersMiddleware', 
    # Debe ir al final: bloquea el login del admin tras varios intentos fallidos
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'core.urls'

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# django-axes: 5 intentos fallidos -> bloqueo de 1 hora para esa IP + usuario
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
# En Vercel la IP real del visitante llega en X-Forwarded-For
AXES_IPWARE_PROXY_COUNT = 1 if EN_PRODUCCION else 0
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]

# Admin: Unfold. Menú, colores e Inicio en core/admin_tema.py
from .admin_tema import UNFOLD  # noqa: E402

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'catalogo.context_processors.sitio',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL)
    }
    # Serverless: sin conexiones persistentes entre invocaciones. Usa la URL con pooler
    # de tu proveedor (Neon: host con '-pooler'; Supabase: puerto 6543).
    DATABASES['default']['CONN_MAX_AGE'] = 0
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True
    DATABASES['default']['OPTIONS'] = {'sslmode': 'require'}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

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


LANGUAGE_CODE = 'es-cl'

TIME_ZONE = 'America/Santiago' 

USE_I18N = True

USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# django-cloudinary-storage 0.3.0 reemplaza el comando collectstatic y todavía lee este
# ajuste, que Django eliminó en 5.1. Django 6 lo ignora (manda STORAGES); solo evita el error.
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Píxeles de publicidad: solo se cargan si el visitante acepta (partials/consentimiento.html)
META_PIXEL_ID = os.environ.get('META_PIXEL_ID', '')
TIKTOK_PIXEL_ID = os.environ.get('TIKTOK_PIXEL_ID', '')
GOOGLE_SITE_VERIFICATION = os.environ.get('GOOGLE_SITE_VERIFICATION', '')

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

WHITENOISE_USE_FINDERS = True
WHITENOISE_MAX_AGE = 86400

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# HTTPS obligatorio solo en Vercel. En local, runserver solo habla HTTP: si esto queda
# en True, Django redirige a https:// y el servidor recibe tráfico TLS que no entiende.
SECURE_SSL_REDIRECT = EN_PRODUCCION
SESSION_COOKIE_SECURE = EN_PRODUCCION
CSRF_COOKIE_SECURE = EN_PRODUCCION
SECURE_HSTS_SECONDS = 31536000 if EN_PRODUCCION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = EN_PRODUCCION
SECURE_HSTS_PRELOAD = EN_PRODUCCION
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')

# Segundo factor del admin (core/admin_2fa.py)
OTP_TOTP_ISSUER = 'Instinto Olfativo'
ADMIN_2FA_OBLIGATORIO = True
