import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
if os.getenv("DJANGO_LOAD_DOTENV", "true").lower() == "true":
    load_dotenv()

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# RUNTIME SAFETY FLAGS (apply early)
# =============================================================================
# Prefer pure-Python protobuf & crc32c to avoid segfaults in forked workers
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("CRC32C_SW_MODE", "1")

# =============================================================================
# URL CONFIGURATION
# =============================================================================

# Public base URL for redirects and QR codes
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

# Parse the public base URL to extract domain and protocol
try:
    parsed_url = urlparse(PUBLIC_BASE_URL)
    if not parsed_url.scheme or not parsed_url.netloc:
        raise ValueError("Invalid URL format")
    PUBLIC_DOMAIN = parsed_url.netloc
    PUBLIC_PROTOCOL = parsed_url.scheme
except (ValueError, AttributeError) as e:
    # Fallback to safe defaults if URL parsing fails
    PUBLIC_BASE_URL = "http://127.0.0.1:8000"
    parsed_url = urlparse(PUBLIC_BASE_URL)
    PUBLIC_DOMAIN = parsed_url.netloc
    PUBLIC_PROTOCOL = parsed_url.scheme

# Generate trusted origins based on PUBLIC_BASE_URL
def get_trusted_origins():
    origins = [PUBLIC_BASE_URL]
    
    # Add www subdomain if not already present
    if not PUBLIC_DOMAIN.startswith('www.'):
        www_domain = f"www.{PUBLIC_DOMAIN}"
        origins.append(f"{PUBLIC_PROTOCOL}://{www_domain}")
    
    # For development: always include localhost variants
    if DEBUG or PUBLIC_DOMAIN.startswith(('127.0.0.1', 'localhost')):
        origins.extend([
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",  # Common React dev server port
            "http://localhost:3000",
        ])
    
    return list(set(origins))  # Remove duplicates

# Generate API server URLs for documentation
def get_api_servers():
    servers = [{"url": PUBLIC_BASE_URL}]
    
    # Add www subdomain if not already present
    if not PUBLIC_DOMAIN.startswith('www.'):
        www_domain = f"www.{PUBLIC_DOMAIN}"
        servers.append({"url": f"{PUBLIC_PROTOCOL}://{www_domain}"})
    
    return servers

# =============================================================================
# CORE DJANGO SETTINGS
# =============================================================================

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in ("true", "1", "yes")
ALLOWED_HOSTS = os.getenv(
    "DJANGO_ALLOWED_HOSTS",
    "horangprint.site,127.0.0.1,localhost"
).split(",")

ROOT_URLCONF = "tiger_photo.urls"
WSGI_APPLICATION = "tiger_photo.wsgi.application"

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party apps
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    # Local apps
    "image",
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
]

# =============================================================================
# DATABASE
# =============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv("DB_NAME", "tiger_photo_db"),
        'USER': os.getenv("DB_USER", "tiger_photo_user"),
        'PASSWORD': os.getenv("DB_PASSWORD", "default_password"),
        'HOST': os.getenv("DB_HOST", "localhost"),
        'PORT': os.getenv("DB_PORT", "5432"),
        'OPTIONS': {
            'sslmode': 'prefer',  # Use SSL when available
        },
    }
}

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC FILES AND MEDIA
# =============================================================================

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# =============================================================================
# TEMPLATES
# =============================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
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

# =============================================================================
# REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Native app optimizations
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # Native apps typically don't need session authentication
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        # Add API key authentication if needed
        # "rest_framework.authentication.TokenAuthentication",
    ],
    # No rate limiting for mobile photobooths with dynamic IPs
    # Rate limiting can be implemented at application level if needed
}

if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ]

# =============================================================================
# API DOCUMENTATION
# =============================================================================

SPECTACULAR_SETTINGS = {
    "TITLE": "Tiger Photo API",
    "DESCRIPTION": "AI 변환/최종 이미지/QR 세션 API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVERS": get_api_servers(),
}

# =============================================================================
# CORS SETTINGS (Hybrid: Photobooth + Web Clients)
# =============================================================================

# Note: CORS is needed for web clients, not for photobooth native apps
# This is a hybrid system with both photobooth APIs and web client APIs

# Web client origins (for CORS)
WEB_CLIENT_ORIGINS = [
    # Add web client domains here
    # Example: "https://admin.horangprint.site",
    # Example: "https://gallery.horangprint.site",
]

# Get additional web client origins from environment
WEB_CLIENT_ORIGINS.extend(
    os.getenv("WEB_CLIENT_ORIGINS", "").split(",") if os.getenv("WEB_CLIENT_ORIGINS") else []
)

# Development: Allow all origins for easier development
# Production: Allow specific web client origins
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False
    # Combine trusted origins with web client origins
    all_web_origins = get_trusted_origins() + WEB_CLIENT_ORIGINS
    CORS_ALLOWED_ORIGINS = [origin for origin in all_web_origins if origin.strip()]
    CORS_ALLOW_CREDENTIALS = True

# CORS headers for web clients
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'x-csrftoken',
    'x-requested-with',
    'x-device-id',        # For photobooth identification
    'x-photobooth-version', # For version tracking
]

# CORS methods for web clients
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

# CSRF settings (for web clients only)
CSRF_TRUSTED_ORIGINS = get_trusted_origins()

# Add web client origins to CSRF trusted origins
if WEB_CLIENT_ORIGINS:
    CSRF_TRUSTED_ORIGINS.extend(WEB_CLIENT_ORIGINS)
    CSRF_TRUSTED_ORIGINS = list(set(CSRF_TRUSTED_ORIGINS))  # Remove duplicates

# Development: Allow CSRF from localhost
if DEBUG:
    CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript access for development
    CSRF_USE_SESSIONS = False
else:
    CSRF_COOKIE_HTTPONLY = True
    CSRF_USE_SESSIONS = True

# CSRF exemption for photobooth APIs (if needed)
# Note: Photobooth native apps typically don't need CSRF protection
CSRF_EXEMPT_URLS = [
    # Add photobooth API URLs that should be exempt from CSRF
    # Example: r'^api/photos/upload/$',
]

# Proxy settings for HTTPS behind reverse proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Security settings that apply to both environments
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Production-only security settings
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    # Development settings
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TASK_ALWAYS_EAGER = False

# =============================================================================
# REDIS CONFIGURATION
# =============================================================================

REDIS_URL = os.getenv("REDIS_URL", CELERY_BROKER_URL)

# =============================================================================
# APPLICATION SPECIFIC SETTINGS
# =============================================================================

# Google Cloud Storage Configuration
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# GCS Project and additional settings
GCS_PROJECT_ID = os.getenv("GCS_PROJECT_ID", "")
GCS_LOCATION = os.getenv("GCS_LOCATION", "asia-northeast3")  # Seoul region

# GCP Compute Engine detection
def is_gcp_compute_engine():
    """Check if running on GCP Compute Engine"""
    try:
        import requests
        # Check if metadata service is available (GCP Compute Engine indicator)
        response = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/",
            headers={"Metadata-Flavor": "Google"},
            timeout=1
        )
        return response.status_code == 200
    except:
        return False

# GCP environment detection
IS_GCP_COMPUTE_ENGINE = is_gcp_compute_engine()

# GCP metadata service utilities
def get_gcp_metadata(metadata_path):
    """Get metadata from GCP metadata service"""
    if not IS_GCP_COMPUTE_ENGINE:
        return None
    
    try:
        import requests
        response = requests.get(
            f"http://metadata.google.internal/computeMetadata/v1/{metadata_path}",
            headers={"Metadata-Flavor": "Google"},
            timeout=2
        )
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    return None

# Get GCP project ID from metadata if not set
if IS_GCP_COMPUTE_ENGINE and not GCS_PROJECT_ID:
    GCS_PROJECT_ID = get_gcp_metadata("project/project-id")

# Credentials handling based on environment
if IS_GCP_COMPUTE_ENGINE:
    # On GCP Compute Engine, use metadata service authentication
    # No need for GOOGLE_APPLICATION_CREDENTIALS
    pass
elif GOOGLE_APPLICATION_CREDENTIALS:
    # Local development or other environments with credential file
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS
elif GCS_BUCKET_NAME:
    # GCS is configured but no credentials found
    import warnings
    warnings.warn(
        "GCS_BUCKET_NAME is set but no credentials found. "
        "Make sure you're running on GCP Compute Engine with proper service account, "
        "or set GOOGLE_APPLICATION_CREDENTIALS for local development.",
        UserWarning
    )

# GCS settings for Django
if GCS_BUCKET_NAME:
    # Default file storage to GCS (if using django-storages)
    DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
    GS_BUCKET_NAME = GCS_BUCKET_NAME
    GS_PROJECT_ID = GCS_PROJECT_ID
    GS_LOCATION = GCS_LOCATION
    
    # GCS URL settings (prefer bucket-level access control; do not set object ACLs)
    GS_FILE_OVERWRITE = False
    GS_CACHE_CONTROL = 'public, max-age=3600'  # 1 hour cache
    
    # GCP Compute Engine specific settings
    if IS_GCP_COMPUTE_ENGINE:
        # Use metadata service for authentication (no credential file needed)
        GS_CREDENTIALS = None  # Will use metadata service
    else:
        # Use credential file for local development, building Credentials object
        if GOOGLE_APPLICATION_CREDENTIALS:
            try:
                from google.oauth2 import service_account
                GS_CREDENTIALS = service_account.Credentials.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS)
            except Exception:
                GS_CREDENTIALS = None

# =============================================================================
# HYBRID API CONFIGURATION
# =============================================================================

# Note: Both photobooth and web clients use the same API endpoints
# The difference is in authentication and request headers:
# - Photobooth: Uses device headers (x-device-id, etc.) + API key
# - Web clients: Uses session authentication + CSRF tokens

# API endpoints used by both clients
SHARED_API_ENDPOINTS = [
    '/api/photos/',      # Photo upload/processing
    '/api/sessions/',    # Session management  
    '/api/gallery/',     # Gallery viewing
    '/api/admin/',       # Admin functions
    # Add other shared API endpoints
]

# Optional: Different authentication for different endpoints
# PHOTOBOOTH_ONLY_ENDPOINTS = ['/api/devices/']  # If some endpoints are photobooth-only
# WEB_ONLY_ENDPOINTS = ['/api/users/']           # If some endpoints are web-only

# =============================================================================
# NATIVE APP / PHOTOBOOTH DEVICE SETTINGS
# =============================================================================

# Mobile photobooth settings
PHOTOBOOTH_DEVICE_TIMEOUT = int(os.getenv("PHOTOBOOTH_DEVICE_TIMEOUT", "60"))
PHOTOBOOTH_MAX_RETRIES = int(os.getenv("PHOTOBOOTH_MAX_RETRIES", "5"))
PHOTOBOOTH_HEARTBEAT_INTERVAL = int(os.getenv("PHOTOBOOTH_HEARTBEAT_INTERVAL", "120"))

PHOTOBOOTH_CONNECTION_TIMEOUT = int(os.getenv("PHOTOBOOTH_CONNECTION_TIMEOUT", "30"))  # Connection timeout
PHOTOBOOTH_READ_TIMEOUT = int(os.getenv("PHOTOBOOTH_READ_TIMEOUT", "120"))  # Read timeout for large uploads

# Native app authentication (if needed)
NATIVE_APP_API_KEY = os.getenv("NATIVE_APP_API_KEY", "")
NATIVE_APP_REQUIRE_AUTH = os.getenv("NATIVE_APP_REQUIRE_AUTH", "False").lower() == "true"

# Mobile photobooth specific headers
NATIVE_APP_HEADERS = [
    'x-device-id',           # Unique device identifier
    'x-photobooth-version',  # Software version
    'x-device-type',         # Device model/type
    'x-location-id',         # Current location identifier
    'x-network-type',        # LTE/5G/WiFi
    'x-signal-strength',     # Network signal strength
    'x-api-key',            # For API key authentication
]

# Mobile network specific settings
MOBILE_NETWORK_OPTIMIZATIONS = {
    'enable_compression': True,           # Enable gzip compression
    'chunked_upload': True,              # Enable chunked uploads for large files
    'retry_exponential_backoff': True,   # Exponential backoff for retries
    'connection_pooling': True,          # Reuse connections
}

# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}