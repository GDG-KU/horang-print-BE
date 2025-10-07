import io, mimetypes
from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect, HttpResponseNotFound, StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Session, Style, ImageAsset, AIJob, QRCode
from .serializers import (
    SessionCreateSerializer, ImageUploadSerializer,
    FinalizeSerializer, AIWebhookSerializer, StyleSerializer
)
from .utils.gcs import upload_fileobj, build_object_name, upload_bytes
from .utils.images import get_image_size
from .utils.qr import build_redirect_url
from .tasks import generate_qr_task
from .utils.events import stream_session_events, publish_session_event
from drf_spectacular.utils import (
    extend_schema, OpenApiParameter, OpenApiTypes, OpenApiResponse, OpenApiExample
)

def _generate_slug():
    # 짧고 URL 친화적인 슬러그
    import secrets, string
    alphabet = string.ascii_letters + string.digits + "_"
    return ''.join(secrets.choice(alphabet) for _ in range(9))

class SessionCreateView(APIView):
    @extend_schema(
        tags=["Session"],
        summary="세션 생성",
        request=SessionCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="세션이 생성되고 QR 발급 작업이 큐에 등록됩니다."
            ),
            400: OpenApiResponse(description="유효성 검증 오류")
        },
        examples=[
            OpenApiExample(
                name="create-session-success",
                response_only=True,
                value={
                    "session_uuid": "c1f9c3d6-2a1b-4a1b-9d1c-2f5f7d3a0c1e",
                    "status": "CREATED",
                    "qr": {
                        "slug": "a1b2c3d4e",
                        "redirect_url": "http://127.0.0.1:8000/s/a1b2c3d4e",
                        "status": "PENDING"
                    }
                }
            )
        ]
    )
    def post(self, request):
        s = SessionCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        style = get_object_or_404(Style, id=s.validated_data["style_id"])
        with transaction.atomic():
            qr = QRCode.objects.create(slug=_generate_slug())
            session = Session.objects.create(
                style=style,
                status=Session.Status.CREATED,
                qr=qr
            )
        # QR 이미지는 비동기로 생성
        generate_qr_task.delay(qr.id)

        data = {
            "session_uuid": str(session.uuid),
            "status": session.status,
            "qr": {
                "slug": qr.slug,
                "redirect_url": build_redirect_url(qr.slug),
                "status": qr.status,
                # 이미지 URL은 아직 없을 수 있음
            }
        }
        return Response(data, status=status.HTTP_201_CREATED)

class SessionDetailView(APIView):
    @extend_schema(
        tags=["Session"],
        summary="세션 상세 조회",
        parameters=[
            OpenApiParameter(name="session_uuid", location=OpenApiParameter.PATH, type=str, description="세션 UUID")
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="세션 상태",
                examples=[
                    OpenApiExample(
                        name="session-detail",
                        response_only=True,
                        value={
                            "session_uuid": "c1f9c3d6-2a1b-4a1b-9d1c-2f5f7d3a0c1e",
                            "status": "AI_REQUESTED",
                            "qr": {
                                "slug": "a1b2c3d4e",
                                "redirect_url": "http://127.0.0.1:8000/s/a1b2c3d4e",
                                "status": "READY",
                                "qr_image_url": "https://storage.googleapis.com/bucket/qr/slug.png"
                            }
                        }
                    )
                ]
            ),
            404: OpenApiResponse(description="세션 없음")
        }
    )
    def get(self, request, session_uuid):
        session = get_object_or_404(Session, uuid=session_uuid)
        qr = session.qr
        qr_obj = None
        if qr:
            qr_obj = {
                "slug": qr.slug,
                "redirect_url": build_redirect_url(qr.slug),
                "status": qr.status,
                "qr_image_url": qr.qr_image_public_url or None
            }
        return Response({
            "session_uuid": str(session.uuid),
            "status": session.status,
            "qr": qr_obj
        })

class SessionEventsView(APIView):
    @extend_schema(
        tags=["Session"],
        summary="세션 SSE 이벤트 스트림",
        parameters=[
            OpenApiParameter(name="session_uuid", location=OpenApiParameter.PATH, type=str, description="세션 UUID")
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.STR,
                description="text/event-stream",
                examples=[
                    OpenApiExample(
                        name="progress-event",
                        summary="RUNNING 이벤트",
                        value="""event: progress\n"""
                    ),
                    OpenApiExample(
                        name="progress-data",
                        summary="RUNNING 데이터",
                        value={
                            "status": "RUNNING",
                            "progress_percent": 95,
                            "phase": "string",
                            "message": "string"
                        }
                    ),
                    OpenApiExample(
                        name="completed",
                        summary="완료 이벤트 데이터",
                        value={"status": "SUCCEEDED", "ai_image_url": "https://.../ai_result.png"}
                    ),
                    OpenApiExample(
                        name="failed",
                        summary="실패 이벤트 데이터",
                        value={"status": "FAILED"}
                    )
                ]
            )
        }
    )
    def get(self, request, session_uuid):
        # 존재 확인 후 SSE 연결
        get_object_or_404(Session, uuid=session_uuid)

        def event_stream():
            for chunk in stream_session_events(str(session_uuid)):
                yield chunk

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

class QRStatusView(APIView):
    @extend_schema(
        tags=["QR"],
        summary="QR 상태 조회",
        parameters=[
            OpenApiParameter(name="slug", location=OpenApiParameter.PATH, type=str, description="QR 슬러그")
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="QR 상태",
                examples=[
                    OpenApiExample(
                        name="qr-status",
                        response_only=True,
                        value={
                            "slug": "a1b2c3d4e",
                            "status": "READY",
                            "redirect_url": "http://127.0.0.1:8000/s/a1b2c3d4e",
                            "qr_image_url": "https://storage.googleapis.com/bucket/qr/slug.png",
                            "target_url": "https://storage.googleapis.com/bucket/final/abc.png"
                        }
                    )
                ]
            ),
            404: OpenApiResponse(description="QR 없음")
        }
    )
    def get(self, request, slug):
        qr = get_object_or_404(QRCode, slug=slug)
        return Response({
            "slug": qr.slug,
            "status": qr.status,
            "redirect_url": build_redirect_url(qr.slug),
            "qr_image_url": qr.qr_image_public_url or None,
            "target_url": qr.target_url or None
        })

class ImageUploadView(APIView):
    @extend_schema(
        tags=["Image"],
        summary="원본 이미지 업로드",
        request=ImageUploadSerializer,
        responses={
            201: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="업로드 성공",
                examples=[
                    OpenApiExample(
                        name="image-upload-success",
                        response_only=True,
                        value={
                            "session_status": "UPLOADED",
                            "original_image_url": "https://storage.googleapis.com/bucket/original/abc.png"
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description="유효성 검증 오류"),
            404: OpenApiResponse(description="세션 없음")
        },
        examples=[
            OpenApiExample(
                name="multipart-form",
                summary="multipart/form-data 예시",
                description="이미지는 multipart로 업로드합니다.",
                value={
                    "session_uuid": "c1f9c3d6-2a1b-4a1b-9d1c-2f5f7d3a0c1e",
                    # NOTE: 파일은 Swagger UI에서 'image_file' 필드로 파일 선택합니다.
                }
            )
        ]
    )
    def post(self, request):
        s = ImageUploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        session = get_object_or_404(Session, uuid=s.validated_data["session_uuid"])
        image_file = s.validated_data["image_file"]

        # 업로드
        object_name = build_object_name("original", image_file.name)
        content_type = image_file.content_type or mimetypes.guess_type(image_file.name)[0] or "application/octet-stream"
        gcs_path, public_url = upload_fileobj(image_file, object_name, content_type)

        width, height = get_image_size(image_file)

        ImageAsset.objects.create(
            session=session,
            kind=ImageAsset.Kind.ORIGINAL,
            gcs_path=gcs_path,
            public_url=public_url,
            width=width, height=height,
            mime=content_type,
            size_bytes=getattr(image_file, "size", None)
        )

        session.status = Session.Status.UPLOADED
        session.save(update_fields=["status","updated_at"])

        # (선택) 여기서 AIJob 생성 및 외부팀 호출 트리거 가능
        # job = AIJob.objects.create(session=session, status=AIJob.Status.PENDING, request_payload={...})
        # 외부 호출 후 request_id 저장

        return Response({
            "session_status": session.status,
            "original_image_url": public_url
        }, status=status.HTTP_201_CREATED)

class FinalizeView(APIView):
    @extend_schema(
        tags=["Image"],
        summary="최종 이미지 업로드 및 QR 타깃 연결",
        request=FinalizeSerializer,
        responses={
            201: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="최종 업로드 성공",
                examples=[
                    OpenApiExample(
                        name="finalize-success",
                        response_only=True,
                        value={
                            "final_image": {"public_url": "https://storage.googleapis.com/bucket/final/abc.png"},
                            "qr": {
                                "redirect_url": "http://127.0.0.1:8000/s/a1b2c3d4e",
                                "qr_image_url": "https://storage.googleapis.com/bucket/qr/slug.png"
                            },
                            "session_status": "FINALIZED"
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description="유효성 검증 오류"),
            404: OpenApiResponse(description="세션 없음")
        },
        examples=[
            OpenApiExample(
                name="multipart-form",
                summary="multipart/form-data 예시",
                description="이미지는 multipart로 업로드합니다.",
                value={
                    "session_uuid": "c1f9c3d6-2a1b-4a1b-9d1c-2f5f7d3a0c1e"
                    # NOTE: Swagger UI에서 'edited_image' 파일을 선택하세요.
                }
            )
        ]
    )
    def post(self, request):
        s = FinalizeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        session = get_object_or_404(Session, uuid=s.validated_data["session_uuid"])
        edited_image = s.validated_data["edited_image"]

        object_name = build_object_name("final", edited_image.name)
        content_type = edited_image.content_type or mimetypes.guess_type(edited_image.name)[0] or "image/png"
        gcs_path, public_url = upload_fileobj(edited_image, object_name, content_type)

        # 최종 이미지는 세션당 1개 제약(모델 제약으로 보호)
        ImageAsset.objects.create(
            session=session,
            kind=ImageAsset.Kind.FINAL,
            gcs_path=gcs_path,
            public_url=public_url,
            mime=content_type,
            size_bytes=getattr(edited_image, "size", None)
        )

        # QR target 연결
        if session.qr:
            session.qr.target_url = public_url
            # 만약 QR 이미지가 아직 없거나 실패했다면 여기서 동기 생성 폴백도 가능:
            # if session.qr.status != QRCode.Status.READY:
            #     from .tasks import generate_qr_task
            #     generate_qr_task(qr_id=session.qr.id)
            session.qr.save(update_fields=["target_url","updated_at"])

        session.status = Session.Status.FINALIZED
        session.save(update_fields=["status","updated_at"])

        return Response({
            "final_image": {"public_url": public_url},
            "qr": {
                "redirect_url": build_redirect_url(session.qr.slug) if session.qr else None,
                "qr_image_url": session.qr.qr_image_public_url if session.qr else None
            },
            "session_status": session.status
        }, status=status.HTTP_201_CREATED)

class AIWebhookView(APIView):
    """
    외부 AI팀이 변환 완료 후 호출하는 콜백 예시
    """
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        tags=["AI"],
        summary="외부 AI 콜백",
        request=AIWebhookSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="수신 성공",
                examples=[
                    OpenApiExample(
                        name="running",
                        summary="진행 중 업데이트",
                        response_only=False,
                        value={
                            "request_id": "job_123",
                            "status": "RUNNING",
                            "progress_percent": 42,
                            "phase": "upscaling",
                            "message": "denoise pass 2/3"
                        }
                    ),
                    OpenApiExample(
                        name="succeeded",
                        summary="완료",
                        response_only=False,
                        value={
                            "request_id": "job_123",
                            "status": "SUCCEEDED",
                            "image_url": "https://ai.example.com/outputs/job_123.png"
                        }
                    ),
                    OpenApiExample(
                        name="failed",
                        summary="실패",
                        response_only=False,
                        value={
                            "request_id": "job_123",
                            "status": "FAILED",
                            "meta": {"error_code": "OOM", "detail": "out of memory"}
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description="유효성 검증 오류"),
            404: OpenApiResponse(description="리소스 없음")
        }
    )
    def post(self, request):
        s = AIWebhookSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        request_id = s.validated_data["request_id"]
        status_str = s.validated_data["status"]
        image_url = s.validated_data.get("image_url")

        job = get_object_or_404(AIJob, request_id=request_id)
        job.response_payload = s.validated_data

        if status_str == "RUNNING":
            job.status = AIJob.Status.RUNNING
            job.response_payload = s.validated_data
            job.save(update_fields=["status","response_payload","updated_at"])
            publish_session_event(str(job.session.uuid), "progress", {
                "status": job.status,
                "progress_percent": s.validated_data.get("progress_percent"),
                "phase": s.validated_data.get("phase"),
                "message": s.validated_data.get("message"),
            })
            return Response({"ok": True})

        if status_str == "SUCCEEDED" and image_url:
            # 외부 URL을 받아 우리 GCS로 저장(간단히 프록시 저장: 다운로드 후 업로드가 이상적이나
            # 여기선 샘플로 URL 원문을 저장했다고 가정하거나, 별도 파이프라인으로 처리)
            # 데모: QR 코드 PNG 같은 바이트 업로드 예시처럼 흉내
            import requests
            r = requests.get(image_url, timeout=10)
            r.raise_for_status()
            object_name = build_object_name("ai", "ai_result.png")
            gcs_path, public_url = upload_bytes(r.content, object_name, "image/png")
            asset = ImageAsset.objects.create(
                session=job.session,
                kind=ImageAsset.Kind.AI,
                gcs_path=gcs_path,
                public_url=public_url,
                mime="image/png",
                size_bytes=len(r.content)
            )
            job.ai_image = asset
            job.status = AIJob.Status.SUCCEEDED

            # 세션 상태 업데이트
            job.session.status = Session.Status.AI_READY
            job.session.save(update_fields=["status","updated_at"])

            job.save(update_fields=["response_payload","ai_image","status","updated_at"])
            publish_session_event(str(job.session.uuid), "completed", {
                "status": job.status,
                "ai_image_url": asset.public_url,
            })
        else:
            job.status = AIJob.Status.FAILED
            job.session.status = Session.Status.FAILED
            job.session.save(update_fields=["status","updated_at"])

            job.save(update_fields=["response_payload","ai_image","status","updated_at"])
            publish_session_event(str(job.session.uuid), "failed", {
                "status": job.status,
            })
        return Response({"ok": True})

def redirect_by_slug(request, slug: str):
    qr = QRCode.objects.filter(slug=slug).first()
    if not qr:
        return HttpResponseNotFound("QR not found")
    if qr.target_url:
        return HttpResponseRedirect(qr.target_url)
    # 아직 타깃이 없으면 대기 페이지(간단 404 메시지로 대체)
    return HttpResponseNotFound("Your image is not ready yet.")

class StyleListView(APIView):
    @extend_schema(
        tags=["Style"],
        summary="스타일 목록 조회",
        responses={
            200: OpenApiResponse(
                response=StyleSerializer(many=True),
                description="스타일 목록",
                examples=[
                    OpenApiExample(
                        name="styles",
                        response_only=True,
                        value=[
                            {"id": 1, "code": "cartoon_v1", "name": "Cartoon", "description": "...", "is_active": True},
                            {"id": 2, "code": "sketch_v2", "name": "Sketch", "description": "...", "is_active": True}
                        ]
                    )
                ]
            )
        }
    )
    def get(self, request):
        qs = Style.objects.filter(is_active=True).order_by("id")
        return Response(StyleSerializer(qs, many=True).data)
