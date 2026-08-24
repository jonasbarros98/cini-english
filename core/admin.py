from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from .models import Student, Lesson, Invoice, FinancialEntry, UserProfile, LessonPlan, LessonPlanAttachment, BillingLog, Subscription, StripeEvent, DayNote, SupportTicket, PublicBookingRequest, TeacherMaterial, BlogCategory, BlogPost


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


# ══════════════════════════════════════════════════════════════════════════
# BLOG
#
# É daqui que o blog é operado: escrever, agendar e ver a fila. O plano é uma
# ou duas postagens por dia, então as ações de agendamento estão à mão, e a
# coluna "Situação" responde de relance a única pergunta que importa numa
# segunda-feira: o que já está no ar, o que sai hoje, e o que ainda é rascunho.
# ══════════════════════════════════════════════════════════════════════════


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order", "artigos_publicados")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("order", "name")

    def artigos_publicados(self, obj):
        return obj.posts.filter(status=BlogPost.STATUS_PUBLISHED).count()

    artigos_publicados.short_description = "Artigos"


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "situacao", "quando", "reading_minutes", "views")
    list_filter = ("status", "category", "featured", "author_name")
    search_fields = ("title", "dek", "content", "keywords", "slug")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    readonly_fields = ("views", "reading_minutes", "created_at", "updated_at", "endereco")
    list_per_page = 40
    actions = (
        "publicar_agora",
        "voltar_para_rascunho",
        "agendar_um_por_dia",
        "agendar_dois_por_dia",
        "marcar_destaque",
    )

    fieldsets = (
        ("Artigo", {
            "fields": ("title", "slug", "dek", "category", "content"),
        }),
        ("Publicação", {
            "fields": ("status", "published_at", "featured", "endereco",
                       "author_name", "author_role"),
            "description": (
                "Para agendar: marque <b>Publicado</b> e ponha uma data futura. "
                "O artigo entra no ar sozinho na hora marcada, sem ninguém "
                "precisar clicar em nada. <b>Atenção ao fuso:</b> a hora aqui é "
                "UTC, três horas à frente de Brasília. Para sair às 9h de "
                "Brasília, grave 12:00. As ações de agendamento em lote, na "
                "lista, já fazem essa conta."
            ),
        }),
        ("Google e redes sociais", {
            "classes": ("collapse",),
            "fields": ("seo_title", "seo_description", "keywords", "cover", "cover_alt"),
        }),
        ("Convite de cadastro (CTA)", {
            "classes": ("collapse",),
            "fields": ("cta_title", "cta_text", "cta_button"),
            "description": (
                "Vazio usa o convite padrão. Vale a pena escrever um próprio "
                "quando o artigo trata de um problema específico: um texto sobre "
                "cobrança converte melhor com um convite que fala de cobrança."
            ),
        }),
        ("Números", {
            "classes": ("collapse",),
            "fields": ("views", "reading_minutes", "created_at", "updated_at"),
        }),
    )

    @admin.display(description="Situação")
    def situacao(self, obj):
        if obj.is_published:
            return "No ar"
        if obj.is_scheduled:
            return "Agendado"
        return "Rascunho"

    @admin.display(description="Data (Brasília)", ordering="published_at")
    def quando(self, obj):
        from .blog_schedule import formatar_br

        return formatar_br(obj.published_at) if obj.published_at else "sem data"

    @admin.display(description="Endereço")
    def endereco(self, obj):
        if not obj.pk:
            return "definido ao salvar"
        url = obj.get_absolute_url()
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)

    @admin.action(description="Publicar agora")
    def publicar_agora(self, request, queryset):
        n = 0
        for post in queryset:
            post.status = BlogPost.STATUS_PUBLISHED
            post.published_at = timezone.now()
            post.save()
            n += 1
        self.message_user(request, f"{n} artigo(s) no ar agora.")

    @admin.action(description="Voltar para rascunho (tira do ar)")
    def voltar_para_rascunho(self, request, queryset):
        n = queryset.update(status=BlogPost.STATUS_DRAFT)
        self.message_user(request, f"{n} artigo(s) fora do ar.")

    @admin.action(description="Agendar: 1 por dia, 9h, a partir de amanhã")
    def agendar_um_por_dia(self, request, queryset):
        self._agendar(request, queryset, 1)

    @admin.action(description="Agendar: 2 por dia, 9h e 17h30, a partir de amanhã")
    def agendar_dois_por_dia(self, request, queryset):
        self._agendar(request, queryset, 2)

    def _agendar(self, request, queryset, por_dia):
        from .blog_schedule import agendar, formatar_br

        # A ordem da fila é a ordem em que a lista está na tela: o admin já
        # ordena por data de publicação, então dá para reordenar antes.
        plano = agendar(list(queryset), por_dia=por_dia)
        if not plano:
            self.message_user(request, "Nenhum artigo selecionado.", level=messages.WARNING)
            return
        primeiro, ultimo = plano[0], plano[-1]
        self.message_user(
            request,
            f"{len(plano)} artigo(s) na fila, {por_dia} por dia. "
            f"Primeiro: {formatar_br(primeiro[1])}. Último: {formatar_br(ultimo[1])}.",
        )

    @admin.action(description="Marcar como destaque da capa do blog")
    def marcar_destaque(self, request, queryset):
        # Destaque é um só: a capa mostra o mais recente marcado, e deixar
        # vários marcados só cria dúvida na hora de olhar a lista.
        BlogPost.objects.filter(featured=True).update(featured=False)
        n = queryset.update(featured=True)
        self.message_user(request, f"{n} artigo(s) em destaque.")
