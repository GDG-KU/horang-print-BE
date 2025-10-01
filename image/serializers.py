from rest_framework import serializers
from .models import Session, Style

class SessionCreateSerializer(serializers.Serializer):
    style_id = serializers.IntegerField()
    user_preferences = serializers.JSONField(required=False)

class ImageUploadSerializer(serializers.Serializer):
    session_uuid = serializers.UUIDField()
    image_file = serializers.ImageField()

class FinalizeSerializer(serializers.Serializer):
    session_uuid = serializers.UUIDField()
    edited_image = serializers.ImageField()

class AIWebhookSerializer(serializers.Serializer):
    request_id = serializers.CharField()
    status = serializers.ChoiceField(choices=["SUCCEEDED","FAILED"])
    image_url = serializers.URLField(required=False)
    meta = serializers.JSONField(required=False)
