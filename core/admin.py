from django.contrib import admin
from .models import Student, Lesson, Task, Invoice, FinancialEntry, UserProfile, LessonPlan, BillingLog, BillingLog


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "status", "plan_name", "user", "lessons_done", "lessons_total")
    search_fields = ("name", "phone", "email", "guardians", "address", "plan_name", "user__username")
    list_filter = ("status", "user", "preferred_payment_method")

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("date", "time", "student", "user", "title", "status")
    list_filter = ("status", "date", "student", "user")
    search_fields = ("title", "info", "student__name", "user__username")

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "user", "date", "due_date")
    list_filter = ("status", "user", "date")
    search_fields = ("title", "tags", "user__username")

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("student", "month", "amount", "status")
    list_filter = ("status", "month")
    search_fields = ("student__name",)

@admin.register(FinancialEntry)
class FinancialEntryAdmin(admin.ModelAdmin):
    list_display = ("student", "description", "amount", "status", "user", "due_date")
    list_filter = ("status", "due_date", "user")
    search_fields = ("student__name", "description", "user__username")

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "user_profile", "is_admin", "created_at")
    list_filter = ("is_admin", "user_profile")
    search_fields = ("user__username", "user__email")
    filter_horizontal = ("partner_teachers",)

@admin.register(LessonPlan)
class LessonPlanAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "user", "goals", "created_at")
    list_filter = ("date", "student", "user")
    search_fields = ("student__name", "goals", "links", "user__username")
    date_hierarchy = "date"

@admin.register(BillingLog)
class BillingLogAdmin(admin.ModelAdmin):
    list_display = ("financial_entry", "student_name", "user", "message_type", "send_method", "sent_at")
    list_filter = ("message_type", "send_method", "sent_at", "user")
    search_fields = ("financial_entry__student__name", "financial_entry__description", "user__username")
    readonly_fields = ("sent_at",)
    
    def student_name(self, obj):
        return obj.financial_entry.student.name
    student_name.short_description = "Aluno"
