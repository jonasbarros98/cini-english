from django.contrib import admin
from .models import Student, Lesson, Invoice, FinancialEntry, UserProfile, LessonPlan, LessonPlanAttachment, BillingLog, Subscription, StripeEvent, DayNote, SupportTicket, PublicBookingRequest, TeacherMaterial


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "status", "plan_name", "user", "lessons_done", "lessons_total")
    search_fields = ("name", "phone", "email", "guardians", "address", "plan_name", "user__username")
    list_filter = ("status", "user", "preferred_payment_method")

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("date", "time", "student", "user", "title", "status", "realized")
    list_filter = ("status", "realized", "date", "student", "user")
    search_fields = ("title", "info", "student__name", "user__username")

@admin.register(TeacherMaterial)
class TeacherMaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "material_type", "file_size_display", "created_at")
    list_filter = ("material_type", "user", "created_at")
    search_fields = ("title", "tags", "user__username")
    readonly_fields = ("file_size", "created_at", "updated_at")
    date_hierarchy = "created_at"

    def file_size_display(self, obj):
        return obj.get_file_size_display()

    file_size_display.short_description = "Tamanho"


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
    list_display = ("user", "user_profile", "is_admin", "subscription_exempt", "created_at")
    list_filter = ("is_admin", "subscription_exempt", "user_profile")
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
    list_display = ("user", "plan", "status", "is_active_display", "current_period_end", "created_at")
    list_filter = ("plan", "status", "created_at")
    search_fields = ("user__username", "user__email", "stripe_customer_id", "stripe_subscription_id")
    readonly_fields = ("stripe_customer_id", "stripe_subscription_id", "created_at", "updated_at")
    date_hierarchy = "created_at"
    
    def is_active_display(self, obj):
        """Retorna True se o status for 'active'"""
        return obj.status == "active"
    is_active_display.boolean = True
    is_active_display.short_description = "Ativa"


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "processed", "processed_at", "created_at")
    list_filter = ("event_type", "processed", "created_at")
    search_fields = ("event_id", "event_type")
    readonly_fields = ("event_id", "event_type", "event_data", "created_at", "processed_at")
    date_hierarchy = "created_at"


@admin.register(DayNote)
class DayNoteAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "text_preview", "created_at", "updated_at")
    list_filter = ("date", "user", "created_at")
    search_fields = ("user__username", "text")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "date"
    
    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    text_preview.short_description = "Texto"


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_id", "user", "title", "category", "impact", "email_sent", "created_at")
    list_filter = ("category", "impact", "email_sent", "created_at", "user")
    search_fields = ("ticket_id", "title", "description", "user__username", "user__email", "page", "url")
    readonly_fields = ("ticket_id", "created_at", "user", "created_at_local", "timezone")
    fieldsets = (
        ("Informações Básicas", {
            "fields": ("ticket_id", "user", "created_at")
        }),
        ("Problema", {
            "fields": ("category", "impact", "title", "description")
        }),
        ("Contexto", {
            "fields": ("page", "query", "url", "created_at_local", "timezone")
        }),
        ("Email", {
            "fields": ("email_sent", "email_error")
        }),
    )
    date_hierarchy = "created_at"


@admin.register(PublicBookingRequest)
class PublicBookingRequestAdmin(admin.ModelAdmin):
    list_display = ("teacher", "requested_date", "requested_time", "student_name", "student_whatsapp", "status", "created_at")
    list_filter = ("status", "requested_date", "teacher")
    search_fields = ("student_name", "student_email", "teacher__username", "teacher__first_name", "teacher__last_name")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "requested_date"
