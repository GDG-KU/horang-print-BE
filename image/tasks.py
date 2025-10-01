from celery import shared_task
from django.db import transaction
from django.conf import settings
from .models import QRCode
from .utils.qr import make_qr_png, build_redirect_url
from .utils.gcs import upload_bytes

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def generate_qr_task(self, qr_id: int):
    try:
        with transaction.atomic():
            qr = QRCode.objects.select_for_update().get(id=qr_id)
            redirect_url = build_redirect_url(qr.slug)
            png = make_qr_png(redirect_url)
            object_name = f"qr/{qr.slug}.png"
            gcs_path, public_url = upload_bytes(png, object_name, "image/png")
            qr.qr_image_gcs_path = gcs_path
            qr.qr_image_public_url = public_url
            qr.status = QRCode.Status.READY
            qr.error_message = ""
            qr.save(update_fields=["qr_image_gcs_path","qr_image_public_url","status","error_message","updated_at"])
    except Exception as e:
        qr = QRCode.objects.get(id=qr_id)
        qr.status = QRCode.Status.FAILED
        qr.error_message = str(e)[:500]
        qr.save(update_fields=["status","error_message","updated_at"])
        raise
