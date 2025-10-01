import io
import uuid
from typing import Tuple
from django.conf import settings
from google.cloud import storage

def _get_client():
    return storage.Client()  # GOOGLE_APPLICATION_CREDENTIALS 환경변수 사용

def upload_bytes(data: bytes, object_name: str, content_type: str) -> Tuple[str, str]:
    """
    data를 GCS에 업로드.
    return: (gcs_path, public_url)
    """
    bucket_name = settings.GCS_BUCKET_NAME
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    blob.upload_from_string(data, content_type=content_type)
    # 공개 액세스(퍼블릭 버킷이거나 IAM으로 공개) 가정
    public_url = f"https://storage.googleapis.com/{bucket_name}/{object_name}"
    gcs_path = f"gs://{bucket_name}/{object_name}"
    return gcs_path, public_url

def upload_fileobj(fobj, object_name: str, content_type: str) -> Tuple[str, str]:
    data = fobj.read()
    return upload_bytes(data, object_name, content_type)

def build_object_name(prefix: str, filename: str) -> str:
    ext = filename.split(".")[-1].lower() if "." in filename else "bin"
    return f"{prefix}/{uuid.uuid4().hex}.{ext}"
