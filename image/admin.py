from django.contrib import admin
from .models import Style, Session, ImageAsset, AIJob, QRCode

@admin.register(Style)
class StyleAdmin(admin.ModelAdmin):
    list_display = ("id","code","name","is_active","created_at")

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("id","uuid","style","status","qr","created_at")
    search_fields = ("uuid",)

@admin.register(ImageAsset)
class ImageAssetAdmin(admin.ModelAdmin):
    list_display = ("id","session","kind","public_url","created_at")
    list_filter = ("kind",)

@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ("id","session","request_id","status","created_at")
    list_filter = ("status",)

@admin.register(QRCode)
class QRAdmin(admin.ModelAdmin):
    list_display = ("id","slug","status","target_url","qr_image_public_url","created_at")
    list_filter = ("status",)
    search_fields = ("slug",)
