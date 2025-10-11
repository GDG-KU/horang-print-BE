import os
import platform
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tiger_photo.settings")
app = Celery("tiger_photo")
app.config_from_object("django.conf:settings", namespace="CELERY")

# On macOS during development, avoid prefork to prevent segfaults with some C extensions
try:
    from django.conf import settings as dj_settings
    if platform.system() == "Darwin" and getattr(dj_settings, "DEBUG", False):
        app.conf.worker_pool = "solo"
except Exception:
    # If settings aren't ready yet, skip; CLI flags can still override
    pass

app.autodiscover_tasks()
