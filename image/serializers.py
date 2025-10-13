from rest_framework import serializers
from .models import Session, Style

class SessionCreateSerializer(serializers.Serializer):
    style_id = serializers.IntegerField()

class ImageUploadSerializer(serializers.Serializer):
    session_uuid = serializers.UUIDField()
    image_file = serializers.ImageField()

class FinalizeSerializer(serializers.Serializer):
    session_uuid = serializers.UUIDField()
    edited_image = serializers.ImageField()

class AIWebhookSerializer(serializers.Serializer):
    request_id = serializers.CharField()
    status = serializers.ChoiceField(choices=["RUNNING","SUCCEEDED","FAILED"])
    image_url = serializers.URLField(required=False)
    meta = serializers.JSONField(required=False)
    progress_percent = serializers.IntegerField(required=False, min_value=0, max_value=100)
    phase = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True)

class StyleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Style
        fields = ("id","code","name","description","is_active","thumbnail_url")
