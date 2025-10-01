import io, qrcode
from django.conf import settings

def make_qr_png(redirect_url: str) -> bytes:
    qr = qrcode.QRCode(
        version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8, border=2
    )
    qr.add_data(redirect_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def build_redirect_url(slug: str) -> str:
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/s/{slug}"
