from django.contrib import admin
from .models import Student, Lesson, Task, Invoice, FinancialEntry, UserProfile, LessonPlan, LessonPlanAttachment, BillingLog, Subscription, StripeEvent


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

@admin.register(LessonPlanAttachment)
class LessonPlanAttachmentAdmin(admin.ModelAdmin):
    list_display = ("lesson_plan", "original_filename", "file_size", "uploaded_at")
    list_filter = ("uploaded_at", "lesson_plan__student", "lesson_plan__user")
    search_fields = ("original_filename", "lesson_plan__student__name", "lesson_plan__user__username")
    readonly_fields = ("file_size", "uploaded_at")
    date_hierarchy = "uploaded_at"

@admin.register(BillingLog)
class BillingLogAdmin(admin.ModelAdmin):
    list_display = ("financial_entry", "student_name", "user", "message_type", "send_method", "sent_at")
    list_filter = ("message_type", "send_method", "sent_at", "user")
    search_fields = ("financial_entry__student__name", "financial_entry__description", "user__username")
    readonly_fields = ("sent_at",)
    
    def student_name(self, obj):
        return obj.financial_entry.student.name
    student_name.short_description = "Aluno"


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "is_active", "current_period_end", "created_at")
    list_filter = ("plan", "status", "created_at")
    search_fields = ("user__username", "user__email", "stripe_customer_id", "stripe_subscription_id")
    readonly_fields = ("stripe_customer_id", "stripe_subscription_id", "created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "processed", "processed_at", "created_at")
    list_filter = ("event_type", "processed", "created_at")
    search_fields = ("event_id", "event_type")
    readonly_fields = ("event_id", "event_type", "event_data", "created_at", "processed_at")
    date_hierarchy = "created_at"
