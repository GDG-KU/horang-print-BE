from django.urls import path
from .views import (
    SessionCreateView, ImageUploadView, FinalizeView,
    SessionDetailView, QRStatusView, StyleListView,
    SessionEventsView, SessionListView
)

urlpatterns = [
    path("session/create", SessionCreateView.as_view()),
    path("sessions", SessionListView.as_view()),
    path("session/<uuid:session_uuid>", SessionDetailView.as_view()),
    path("session/<uuid:session_uuid>/events", SessionEventsView.as_view()),
    path("qr/<slug:slug>", QRStatusView.as_view()),
    path("image/upload", ImageUploadView.as_view()),
    path("image/finalize", FinalizeView.as_view()),
    path("styles", StyleListView.as_view()),
]
