from django.contrib import admin
from .models import Student, Lesson, Task, Invoice, FinancialEntry, UserProfile, LessonPlan


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

@admin.register(FinancialEntry)
class FinancialEntryAdmin(admin.ModelAdmin):
    list_display = ("student", "description", "amount", "status", "due_date")
    list_filter = ("status", "due_date")
    search_fields = ("student__name", "description")

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_admin", "created_at")
    list_filter = ("is_admin",)
    search_fields = ("user__username", "user__email")

@admin.register(LessonPlan)
class LessonPlanAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "goals", "created_at")
    list_filter = ("date", "student")
    search_fields = ("student__name", "goals", "links")
    date_hierarchy = "date"
