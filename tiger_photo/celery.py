import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tiger_photo.settings")
app = Celery("tiger_photo")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
