import logging
from celery import shared_task
from django.db import transaction
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def generate_qr_task(self, qr_id: int):
    print(f"generate_qr_task: {qr_id}")

    # Lazy imports to avoid Django settings issues
    print(f"importing models")
    from .models import QRCode

    print(f"importing qr")
    from .utils.qr import make_qr_png, build_redirect_url

    print(f"importing gcs")
    from .utils.gcs import upload_bytes
    
    try:
        with transaction.atomic():
            print("generate_qr_task: fetching QRCode id=%s", qr_id)
            qr = QRCode.objects.select_for_update().get(id=qr_id)

            print("generate_qr_task: building redirect URL for slug=%s", qr.slug)
            redirect_url = build_redirect_url(qr.slug)

            logger.info("generate_qr_task: generating PNG for redirect URL")
            png = make_qr_png(redirect_url)

            object_name = f"qr/{qr.slug}.png"
            print("generate_qr_task: uploading to GCS object=%s", object_name)
            gcs_path, public_url = upload_bytes(png, object_name, "image/png")

            print("generate_qr_task: updating QRCode record")
            qr.qr_image_gcs_path = gcs_path
            qr.qr_image_public_url = public_url
            qr.status = QRCode.Status.READY
            qr.error_message = ""
            qr.save(update_fields=["qr_image_gcs_path","qr_image_public_url","status","error_message","updated_at"])
    except Exception as e:
        # Import here to avoid circular import issues
        from .models import QRCode
        try:
            qr = QRCode.objects.get(id=qr_id)
            qr.status = QRCode.Status.FAILED
            qr.error_message = str(e)[:500]
            qr.save(update_fields=["status","error_message","updated_at"])
        except Exception:
            # If even this fails, at least log the original error
            logger.exception("generate_qr_task: failed with exception before updating model")
        raise
