import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "corsheaders", "rest_framework", "image",
    "drf_spectacular",
    "drf_spectacular_sidecar"
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

ROOT_URLCONF = "tiger_photo.urls"
WSGI_APPLICATION = "tiger_photo.wsgi.application"

# PostgreSQL (사용자가 준 설정 그대로)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv("DB_NAME", "tiger_photo_db"),
        'USER': os.getenv("DB_USER", "tiger_photo_user"),
        'PASSWORD': os.getenv("DB_PASSWORD", "default_password"),
        'HOST': os.getenv("DB_HOST", "localhost"),
        'PORT': os.getenv("DB_PORT", "5432"),
    }
}

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

REST_FRAMEWORK = {
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
}

CORS_ALLOW_ALL_ORIGINS = True

# GCS
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")

# Public base url (리다이렉트/QR 내용에 사용)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

# Celery
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TASK_ALWAYS_EAGER = False  # 개발에서 동기 실행하려면 True

# Redis for SSE/pubsub (fallback to Celery broker)
REDIS_URL = os.getenv("REDIS_URL", CELERY_BROKER_URL)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],   # 직접 만든 템플릿 디렉토리 (없으면 [])
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


REST_FRAMEWORK.update({
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
})

SPECTACULAR_SETTINGS = {
    "TITLE": "Tiger Photo API",
    "DESCRIPTION": "AI 변환/최종 이미지/QR 세션 API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,  # /schema/ 경로는 따로 열어주므로 False 권장
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVERS": [{"url": "http://34.50.8.24"}],  # 필요시 prod/staging 추가
    # 인증 쓰면 여기에 SECURITY_SCHEMES 정의 가능 (예: JWT)
}
