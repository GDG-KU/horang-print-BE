# your_app_name/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny  # 필요시 권한 변경
from .models import Student, Department
from .serializers import StudentSerializer, DepartmentSerializer
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all().order_by('id')
    serializer_class = DepartmentSerializer
    permission_classes = [AllowAny]


@extend_schema_view(
    list=extend_schema(
        summary="학생 목록 조회",
        tags=["Practice-Student"],
        parameters=[
            OpenApiParameter(name="department", type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, description="부서 ID 필터"),
            OpenApiParameter(name="name", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="이름 부분검색")
        ]
    ),
    retrieve=extend_schema(tags=["Practice-Student"]),
    create=extend_schema(tags=["Practice-Student"]),
    update=extend_schema(tags=["Practice-Student"]),
    partial_update=extend_schema(tags=["Practice-Student"]),
    destroy=extend_schema(tags=["Practice-Student"])
)
class StudentViewSet(viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Student.objects.select_related('department').order_by('id')
        # /api/students/?department=3 처럼 부서별 필터 지원
        dept_id = self.request.query_params.get('department')
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        # /api/students/?name=홍 처럼 이름 부분검색
        name = self.request.query_params.get('name')
        if name:
            qs = qs.filter(name__icontains=name)
        return qs

    # 필요 시 create/update에서 커스텀 로직 추가 예시
    # def create(self, request, *args, **kwargs):
    #     return super().create(request, *args, **kwargs)
