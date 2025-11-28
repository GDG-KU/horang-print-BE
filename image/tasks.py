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


def _generate_content_default(client, image, prompt: str):
    """Default image generation with a simple prompt."""
    from google.genai import types
    generate_content_config = types.GenerateContentConfig(
        top_p=0.95,
        response_modalities=[
            "IMAGE",
        ],
        image_config=types.ImageConfig(
            image_size="1K",
        ),
    )
    return client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=[image, prompt],
        config=generate_content_config,
    )

def pil_to_bytes(img) -> bytes:
    import io
    from PIL import Image
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def _generate_content_animal_crossing(client, user_image, prompt: str):
    """Image generation for Animal Crossing with a style reference image."""
    import io
    import requests
    from PIL import Image
    from google.genai import types

    ANIMAL_CROSSING_STYLE_IMAGE_URL = "https://file.horangprint.site/ref/animal_crossing_style.png"

    resp = requests.get(ANIMAL_CROSSING_STYLE_IMAGE_URL, timeout=20)
    resp.raise_for_status()
    style_image = Image.open(io.BytesIO(resp.content)).convert("RGBA")

    user_img_bytes = pil_to_bytes(user_image.convert("RGBA"))
    style_img_bytes = pil_to_bytes(style_image)

    generate_content_config = types.GenerateContentConfig(
        top_p=0.8,
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(
            image_size="1K",
        ),
    )

    # Build multi-part content
    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "text": "Use the second image as the style reference (Animal Crossing style). "
                    + prompt
                },
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": style_img_bytes,
                    }
                },
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": user_img_bytes,
                    }
                },
            ],
        }
    ]

    return client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=contents,
        config=generate_content_config,
    )


@shared_task(bind=True, max_retries=0)
def run_ai_generation_task(self, ai_job_id: int):
    """Run Gemini-based image generation for a given AIJob."""
    # Lazy imports to avoid Django app loading issues
    from django.db import transaction
    from .models import AIJob, ImageAsset, Session
    from .utils.gcs import upload_bytes
    from .utils.events import publish_session_event
    from django.conf import settings
    import io
    import requests
    from PIL import Image

    try:
        # Mark job as RUNNING
        with transaction.atomic():
            job = AIJob.objects.select_for_update().get(id=ai_job_id)
            job.status = AIJob.Status.RUNNING
            job.save(update_fields=["status", "updated_at"])

        # Notify clients that AI generation has started
        publish_session_event(str(job.session.uuid), "progress", {
            "status": job.status,
            "message": "AI generation started"
        })

        # Fetch original image bytes
        original = ImageAsset.objects.filter(
            session=job.session,
            kind=ImageAsset.Kind.ORIGINAL
        ).order_by("-id").first()
        if not original or not original.public_url:
            raise ValueError("Original image not found for session")

        resp = requests.get(original.public_url, timeout=20)
        resp.raise_for_status()
        image = Image.open(io.BytesIO(resp.content))

        # Build prompt from Style.prompt (fallback to description/name)
        style = job.session.style
        prompt = (getattr(style, "prompt", None) or style.description or style.name or "Transform the photo")[:4000]
        #prompt = prompt.encode("ascii", "ignore").decode("ascii")

        # Call Gemini to generate content
        from google import genai
        api_key = getattr(settings, "GOOGLE_GENAI_API_KEY", None)
        if not api_key:
            raise ValueError("GOOGLE_GENAI_API_KEY not configured")

        client = genai.Client(api_key=api_key)

        # Choose generation function based on style
        if style and style.code and "animal-crossing" in style.code:
            logger.info("Using Animal Crossing style generation for job %d", ai_job_id)
            response = _generate_content_animal_crossing(client, image, prompt)
        else:
            logger.info("Using default style generation for job %d", ai_job_id)
            response = _generate_content_default(client, image, prompt)

        # Extract resulting image bytes
        image_bytes_list = []
        if response and getattr(response, "candidates", None):
            first = response.candidates[0]
            for part in getattr(first.content, "parts", []) or []:
                if getattr(part, "inline_data", None):
                    image_bytes_list.append(part.inline_data.data)

        if not image_bytes_list:
            raise ValueError("No image returned from AI")

        result_bytes = image_bytes_list[0]

        # Upload result to GCS and create ImageAsset
        object_name = f"ai/{job.session.uuid}.png"
        gcs_path, public_url = upload_bytes(result_bytes, object_name, "image/png")
        asset = ImageAsset.objects.create(
            session=job.session,
            kind=ImageAsset.Kind.AI,
            gcs_path=gcs_path,
            public_url=public_url,
            mime="image/png",
            size_bytes=len(result_bytes),
        )

        # Update job and session
        with transaction.atomic():
            job.ai_image = asset
            job.status = AIJob.Status.SUCCEEDED
            job.save(update_fields=["ai_image", "status", "updated_at"])

            job.session.status = Session.Status.AI_READY
            job.session.save(update_fields=["status", "updated_at"])

        # Publish completion event
        publish_session_event(str(job.session.uuid), "completed", {
            "status": job.status,
            "ai_image_url": asset.public_url,
        })

    except Exception as e:
        logger.exception("run_ai_generation_task failed: %s", e)
        try:
            job = AIJob.objects.get(id=ai_job_id)
            job.status = AIJob.Status.FAILED
            job.save(update_fields=["status", "updated_at"])

            job.session.status = Session.Status.FAILED
            job.session.save(update_fields=["status", "updated_at"])

            publish_session_event(str(job.session.uuid), "failed", {
                "status": job.status,
                "message": str(e),
            })
        except Exception:
            # best-effort update
            pass
        raise
