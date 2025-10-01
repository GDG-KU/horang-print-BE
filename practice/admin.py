from django.contrib import admin

# Register your models here.
from .models import Student, Department

admin.site.register(Student)
admin.site.register(Department)