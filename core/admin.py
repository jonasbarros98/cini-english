from django.contrib import admin
from .models import Student, Lesson, Task, Invoice  # ajuste se os nomes forem diferentes


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "plan_name", "lessons_done", "lessons_total", "active")
    search_fields = ("name", "phone", "guardians", "address", "plan_name")
    list_filter = ("active",)

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("date", "time", "student", "title", "status")
    list_filter = ("status", "date", "student")
    search_fields = ("title", "info", "student__name")

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status")
    list_filter = ("status",)
    search_fields = ("title", "tags")

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("student", "month", "amount", "status")
    list_filter = ("status", "month")
    search_fields = ("student__name",)
