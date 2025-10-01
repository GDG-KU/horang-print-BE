# your_app_name/serializers.py
from rest_framework import serializers
from .models import Student, Department

class StudentSerializer(serializers.ModelSerializer):
    # 읽기 편하도록 부가 정보
    department_name = serializers.ReadOnlyField(source='department.name')

    class Meta:
        model = Student
        fields = ['id', 'name', 'age', 'grade', 'department', 'department_name']
        read_only_fields = ['id', 'department_name']


class DepartmentSerializer(serializers.ModelSerializer):
    # 부서 상세 조회 시 소속 학생 목록도 같이 보고 싶을 때
    students = StudentSerializer(many=True, read_only=True)

    class Meta:
        model = Department
        fields = ['id', 'name', 'location', 'students']
        read_only_fields = ['id', 'students']
