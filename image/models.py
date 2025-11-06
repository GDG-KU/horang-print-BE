import uuid as uuidlib
from django.db import models

class Style(models.Model):
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    prompt = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    thumbnail_url = models.URLField(max_length=1024, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return f"{self.name}({self.code})"

class QRCode(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "PENDING"
        READY = "READY", "READY"
        FAILED = "FAILED", "FAILED"

    slug = models.SlugField(max_length=32, unique=True, db_index=True)
    qr_image_gcs_path = models.CharField(max_length=512, blank=True)
    qr_image_public_url = models.URLField(max_length=1024, blank=True)
    target_url = models.URLField(max_length=1024, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    error_message = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return f"QR[{self.slug}] {self.status}"

class Session(models.Model):
    class Status(models.TextChoices):
        CREATED="CREATED","CREATED"
        UPLOADED="UPLOADED","UPLOADED"
        AI_REQUESTED="AI_REQUESTED","AI_REQUESTED"
        AI_READY="AI_READY","AI_READY"
        DECORATING="DECORATING","DECORATING"
        FINALIZED="FINALIZED","FINALIZED"
        FAILED="FAILED","FAILED"

    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, db_index=True, editable=False)
    style = models.ForeignKey(Style, on_delete=models.PROTECT)
    user_preferences = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CREATED, db_index=True)
    qr = models.OneToOneField(QRCode, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return f"Session[{self.uuid}] {self.status}"

class ImageAsset(models.Model):
    class Kind(models.TextChoices):
        ORIGINAL="ORIGINAL","ORIGINAL"
        AI="AI","AI"
        FINAL="FINAL","FINAL"

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="images", db_index=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)
    gcs_path = models.CharField(max_length=512)
    public_url = models.URLField(max_length=1024, null=True, blank=True, db_index=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    mime = models.CharField(max_length=64, null=True, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'kind'],
                name='uniq_final_per_session',
                condition=models.Q(kind='FINAL')
            )
        ]

class AIJob(models.Model):
    class Status(models.TextChoices):
        PENDING="PENDING","PENDING"
        RUNNING="RUNNING","RUNNING"
        SUCCEEDED="SUCCEEDED","SUCCEEDED"
        FAILED="FAILED","FAILED"

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='ai_jobs', db_index=True)
    request_id = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
    request_payload = models.JSONField()
    response_payload = models.JSONField(null=True, blank=True)
    ai_image = models.OneToOneField(ImageAsset, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
