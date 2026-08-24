from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date
from django.utils import timezone
import secrets

class Student(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_ENDED = "ended"
    
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Ativo"),
        (STATUS_PAUSED, "Pausado"),
        (STATUS_ENDED, "Encerrado"),
    ]
    
    PAYMENT_METHOD_PIX = "pix"
    PAYMENT_METHOD_CARD = "card"
    PAYMENT_METHOD_CASH = "cash"
    PAYMENT_METHOD_TRANSFER = "transfer"
    
    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_PIX, "PIX"),
        (PAYMENT_METHOD_CARD, "Cartão"),
        (PAYMENT_METHOD_CASH, "Dinheiro"),
        (PAYMENT_METHOD_TRANSFER, "Transferência"),
    ]

    BILLING_PACKAGE = "package"
    BILLING_MONTHLY_FIXED = "monthly_fixed"
    BILLING_PER_LESSON = "per_lesson"
    BILLING_OTHER = "other"

    BILLING_TYPE_CHOICES = [
        (BILLING_PACKAGE, "Pacote de aulas"),
        (BILLING_MONTHLY_FIXED, "Mensal fixo"),
        (BILLING_PER_LESSON, "Por aula realizada"),
        (BILLING_OTHER, "Outro"),
    ]

    name = models.CharField(max_length=255)
    guardians = models.CharField(
        max_length=255,
        help_text="Pai/mãe ou 'Responsável próprio'", blank=True
    )
    phone = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True, help_text="E-mail do aluno ou responsável")
    
    # Plano
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        help_text="Status do aluno"
    )
    billing_type = models.CharField(
        max_length=20,
        choices=BILLING_TYPE_CHOICES,
        default=BILLING_PACKAGE,
        help_text="Tipo de cobrança do aluno",
    )
    plan_name = models.CharField(max_length=255, blank=True, help_text="Plano do aluno (pacote)")
    # Nível CEFR (A1–C2): padrão internacional para proficiência em idiomas. Opcional para outros tipos de aula.
    level = models.CharField(
        max_length=3,
        blank=True,
        null=True,
        choices=[
            ("A1", "A1"),
            ("A2", "A2"),
            ("B1", "B1"),
            ("B2", "B2"),
            ("C1", "C1"),
            ("C2", "C2"),
        ],
        help_text="Nível do aluno (CEFR). Usado principalmente por professores de idiomas; opcional para outros.",
    )
    monthly_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Valor mensal fixo (para tipo Mensal fixo)",
    )
    per_lesson_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Valor por aula realizada",
    )
    plan_start_date = models.DateField(null=True, blank=True, help_text="Data de início do plano")
    lessons_total = models.PositiveSmallIntegerField(default=0, help_text="Aulas do plano")
    lessons_done = models.PositiveSmallIntegerField(default=0, help_text="Aulas realizadas")
    default_due_day = models.PositiveSmallIntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text="Dia de vencimento padrão (1 a 28)"
    )
    preferred_payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
        help_text="Forma de pagamento preferida"
    )
    
    teacher_notes = models.TextField(
        blank=True,
        null=True,
        default="",
        help_text="Observações do professor sobre o aluno (visível na ficha do aluno)"
    )

    # Lembrete de fim de pacote: quando faltarem N aulas, o aluno aparece
    # destacado na lista e no dashboard. Vazio significa "usar o padrão do
    # professor" (UserProfile.lesson_alert_default), para o professor não ter
    # de configurar aluno a aluno.
    lesson_alert_threshold = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Avisar quando faltarem N aulas para o pacote acabar. Vazio usa o padrão do professor.",
    )

    # Financeiro
    pix_key = models.CharField(max_length=255, blank=True, help_text="Chave Pix")
    contract_pdf = models.FileField(
        upload_to="contracts/",
        blank=True,
        null=True,
        help_text="Contrato do aluno em PDF"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="students",
        help_text="Professor dono da conta (responsável pelo cadastro do aluno)"
    )
    assigned_teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_students",
        help_text="Professor parceiro que dará as aulas (opcional). Definido pelo dono da conta.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    # ── Fim do pacote de aulas ───────────────────────────────────────────

    @property
    def lessons_realized_count(self):
        """Aulas efetivamente dadas, contadas a partir das aulas do calendário.

        Não usa o campo `lessons_done` de propósito. A tela de alunos sempre
        mostrou a contagem real das aulas com `realized=True`, e o campo do
        modelo pode estar defasado. Com duas fontes, o aviso de fim de pacote
        discordaria do "3/8 aulas" exibido logo ao lado no mesmo card.

        Prefere a contagem anotada pelo queryset, que resolve a lista inteira
        numa query. Sem anotação, conta na hora.
        """
        anotado = getattr(self, "_realizadas", None)
        if anotado is not None:
            return anotado
        return self.lessons.filter(realized=True).count()

    @property
    def lessons_remaining(self):
        """Aulas que faltam no pacote.

        Devolve None quando o aluno não tem pacote com número fechado de
        aulas (mensal fixo, por aula realizada), caso em que "acabar" não
        significa nada e não faz sentido alertar.
        """
        total = self.lessons_total or 0
        if not total:
            return None
        return max(total - self.lessons_realized_count, 0)

    def lesson_alert_at(self, default=2):
        """Limite efetivo deste aluno: o dele, ou o padrão do professor."""
        if self.lesson_alert_threshold is not None:
            return self.lesson_alert_threshold
        return default

    def is_package_ending(self, default=2):
        """True quando o pacote está no fim e vale avisar o professor.

        Só para aluno ativo: pausado ou encerrado não é pendência, é estado
        deliberado, e alertar sobre eles vira ruído que ensina o professor a
        ignorar o aviso.
        """
        if self.status != self.STATUS_ACTIVE:
            return False
        restantes = self.lessons_remaining
        if restantes is None:
            return False
        return restantes <= self.lesson_alert_at(default)


class StudentShareToken(models.Model):
    """
    Token para acesso público (sem login) à "Área do Aluno".
    Cada aluno pode ter no máximo 1 token ativo; ao regenerar, o anterior é revogado.
    """

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="share_tokens")
    token = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    @staticmethod
    def generate_token() -> str:
        # Ex: tok_a1b2c3... (sem caracteres especiais que atrapalhem URL)
        raw = secrets.token_urlsafe(18)
        raw = raw.replace("-", "").replace("_", "")
        return f"tok_{raw}"

    @classmethod
    def get_active_token(cls, student: "Student"):
        return cls.objects.filter(student=student, revoked_at__isnull=True).order_by("-created_at").first()

    @classmethod
    def revoke_active_token(cls, student: "Student"):
        cls.objects.filter(student=student, revoked_at__isnull=True).update(revoked_at=timezone.now())

    @classmethod
    def create_new_active_token(cls, student: "Student"):
        cls.revoke_active_token(student)

        # Retry pequeno por segurança caso colida token por acaso
        for _ in range(5):
            token_val = cls.generate_token()
            if not cls.objects.filter(token=token_val).exists():
                return cls.objects.create(student=student, token=token_val)

        return cls.objects.create(student=student, token=f"tok_{secrets.token_hex(16)}")


class Lesson(models.Model):
    STATUS_CHOICES = [
        ("confirmed", "Confirmada"),
        ("pending", "Pendente"),
        ("canceled", "Cancelada"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="lessons",
        help_text="Professor responsável pela aula"
    )
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    title = models.CharField(max_length=255)
    info = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="pending",
    )
    realized = models.BooleanField(
        default=False,
        help_text="Indica se a aula foi realizada"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "time"]

    def __str__(self) -> str:
        return f"{self.date} - {self.title}"


class StudentHomework(models.Model):
    STATUS_PENDING = "pending"
    STATUS_DONE = "done"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_DONE, "Concluído"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="homeworks",
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="assigned_homeworks",
        help_text="Professor que atribuiu o homework",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    student_response = models.TextField(blank=True, help_text="Resposta/entrega em texto (opcional)")
    teacher_feedback = models.TextField(blank=True, help_text="Feedback do professor (opcional)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Homework do Aluno"
        verbose_name_plural = "Homeworks dos Alunos"

    def __str__(self) -> str:
        return f"{self.student.name} - {self.title}"


class StudentHomeworkMessage(models.Model):
    SENDER_STUDENT = "student"
    SENDER_TEACHER = "teacher"
    SENDER_CHOICES = [
        (SENDER_STUDENT, "Aluno"),
        (SENDER_TEACHER, "Professor"),
    ]

    homework = models.ForeignKey(
        StudentHomework,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message = models.TextField()
    # Para mensagens de professor, registramos o usuário autor.
    # Em mensagens públicas do aluno, esse campo fica nulo.
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_homework_messages",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "Mensagem da Tarefa do Aluno"
        verbose_name_plural = "Mensagens das Tarefas dos Alunos"

    def __str__(self) -> str:
        return f"{self.get_sender_display()} - HW#{self.homework_id}"


class StudentHomeworkMessageRead(models.Model):
    """
    Registro de mensagens "lidas" pelo professor (por usuário).
    Usado para exibir badge/sininho com contagem de mensagens ainda não lidas.
    """

    message = models.ForeignKey(
        StudentHomeworkMessage,
        on_delete=models.CASCADE,
        related_name="reads",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="student_homework_message_reads",
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-read_at", "-id"]
        unique_together = [("message", "user")]
        verbose_name = "Mensagem da Tarefa do Aluno (Lida)"
        verbose_name_plural = "Mensagens das Tarefas dos Alunos (Lidas)"

    def __str__(self) -> str:
        return f"Read by {self.user_id} - HW#{self.message.homework_id}"


class Invoice(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"
    STATUS_REMIND = "remind"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_PAID, "Pago"),
        (STATUS_OVERDUE, "Vencido"),
        (STATUS_REMIND, "Lembrar de cobrar"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="invoices"
    )
    # Usa sempre o dia 1 para representar o mês/ano da cobrança
    month = models.DateField()                      # ex.: 2026-01-01
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-month", "student__name"]
        unique_together = ("student", "month")  # 1 cobrança por aluno/mês

    def __str__(self):
        return f"{self.student.name} - {self.month:%m/%Y} - {self.amount}"


class FinancialEntry(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_PAID, "Pago"),
        (STATUS_OVERDUE, "Vencido"),
        (STATUS_CANCELLED, "Cancelado"),
    ]

    PAYMENT_METHOD_PIX = "pix"
    PAYMENT_METHOD_CASH = "cash"
    PAYMENT_METHOD_CARD = "card"
    PAYMENT_METHOD_TRANSFER = "transfer"
    PAYMENT_METHOD_OTHER = "other"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_PIX, "PIX"),
        (PAYMENT_METHOD_CASH, "Dinheiro"),
        (PAYMENT_METHOD_CARD, "Cartão"),
        (PAYMENT_METHOD_TRANSFER, "Transferência"),
        (PAYMENT_METHOD_OTHER, "Outro"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="financial_entries"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="financial_entries",
        help_text="Professor responsável pelo lançamento financeiro"
    )
    beneficiary_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="beneficiary_financial_entries",
        help_text="Professor que receberá o lançamento (pode ser o próprio criador ou um parceiro)"
    )
    description = models.CharField(max_length=255, help_text="Descrição do lançamento")
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Valor total"
    )
    installments = models.PositiveSmallIntegerField(
        default=1, help_text="Número de parcelas"
    )
    current_installment = models.PositiveSmallIntegerField(
        default=1, help_text="Parcela atual"
    )
    issue_date = models.DateField(help_text="Data do registro (automática)")
    due_date = models.DateField(help_text="Vencimento da 1ª parcela")
    payment_date = models.DateField(
        null=True, blank=True, help_text="Data do pagamento"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_METHOD_PIX,
        blank=True,
    )
    notes = models.TextField(blank=True, help_text="Observações")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lançamento Financeiro"
        verbose_name_plural = "Lançamentos Financeiros"
        ordering = ["-due_date", "student__name"]

    def __str__(self):
        return f"{self.student.name} - {self.description} - {self.amount}"


class BillingLog(models.Model):
    """Registro de cobranças enviadas aos alunos"""
    
    MESSAGE_TYPE_FRIENDLY = "friendly"
    MESSAGE_TYPE_DUE_TODAY = "due_today"
    MESSAGE_TYPE_OVERDUE = "overdue"
    MESSAGE_TYPE_THANK_YOU = "thank_you"
    
    MESSAGE_TYPE_CHOICES = [
        (MESSAGE_TYPE_FRIENDLY, "Lembrete amigável"),
        (MESSAGE_TYPE_DUE_TODAY, "Vence hoje"),
        (MESSAGE_TYPE_OVERDUE, "Em atraso"),
        (MESSAGE_TYPE_THANK_YOU, "Agradecimento"),
    ]
    
    SEND_METHOD_WHATSAPP = "whatsapp"
    SEND_METHOD_EMAIL = "email"
    SEND_METHOD_SMS = "sms"
    SEND_METHOD_OTHER = "other"
    
    SEND_METHOD_CHOICES = [
        (SEND_METHOD_WHATSAPP, "WhatsApp"),
        (SEND_METHOD_EMAIL, "E-mail"),
        (SEND_METHOD_SMS, "SMS"),
        (SEND_METHOD_OTHER, "Outro"),
    ]
    
    financial_entry = models.ForeignKey(
        FinancialEntry,
        on_delete=models.CASCADE,
        related_name="billing_logs",
        help_text="Lançamento financeiro cobrado"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="billing_logs",
        help_text="Professor que realizou a cobrança"
    )
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE_CHOICES,
        help_text="Tipo de mensagem enviada"
    )
    send_method = models.CharField(
        max_length=20,
        choices=SEND_METHOD_CHOICES,
        default=SEND_METHOD_WHATSAPP,
        help_text="Método de envio"
    )
    message_content = models.TextField(
        help_text="Conteúdo da mensagem enviada"
    )
    sent_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Data e hora do envio"
    )
    
    class Meta:
        ordering = ["-sent_at"]
        verbose_name = "Log de Cobrança"
        verbose_name_plural = "Logs de Cobrança"
    
    def __str__(self) -> str:
        return f"{self.financial_entry.student.name} - {self.message_type} - {self.sent_at:%d/%m/%Y %H:%M}"


class LessonPlan(models.Model):
    """Planejamento de aulas por aluno"""
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="lesson_plans",
        help_text="Aluno para o qual este planejamento é destinado"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="lesson_plans",
        help_text="Professor responsável pelo planejamento"
    )
    date = models.DateField(help_text="Data da aula planejada")
    links = models.TextField(
        blank=True,
        help_text="Links separados por quebra de linha (Google Slides, YouTube, etc.)"
    )
    goals = models.TextField(
        blank=True,
        help_text="Objetivos e metas da aula"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "student__name"]
        verbose_name = "Planejamento de Aula"
        verbose_name_plural = "Planejamentos de Aulas"

    def __str__(self):
        return f"{self.student.name} - {self.date}"

    def get_links_list(self):
        """Retorna os links como uma lista"""
        if not self.links:
            return []
        return [link.strip() for link in self.links.split('\n') if link.strip()]


class LessonPlanAttachment(models.Model):
    """Anexos de documentos para planejamentos de aulas"""
    lesson_plan = models.ForeignKey(
        LessonPlan,
        on_delete=models.CASCADE,
        related_name="attachments",
        help_text="Planejamento ao qual este anexo pertence"
    )
    file = models.FileField(
        upload_to="lesson_plan_attachments/%Y/%m/",
        help_text="Arquivo anexado (PDF, Word, Excel, etc.)"
    )
    original_filename = models.CharField(
        max_length=255,
        help_text="Nome original do arquivo"
    )
    file_size = models.PositiveIntegerField(
        help_text="Tamanho do arquivo em bytes"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Anexo de Planejamento"
        verbose_name_plural = "Anexos de Planejamentos"

    def __str__(self):
        return f"{self.lesson_plan.student.name} - {self.original_filename}"

    def get_file_size_display(self):
        """Retorna o tamanho do arquivo formatado"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class StudentMaterial(models.Model):
    """Materiais compartilhados com o aluno na aba Materiais (independente de Planejamento)."""
    TYPE_FILE = "file"
    TYPE_LINK = "link"
    TYPE_CHOICES = [
        (TYPE_FILE, "Arquivo"),
        (TYPE_LINK, "Link"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="materials",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="student_materials",
        help_text="Professor que criou o material",
    )
    title = models.CharField(max_length=200, help_text="Título exibido para o aluno")
    material_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_FILE)
    file = models.FileField(upload_to="student_materials/%Y/%m/", blank=True, null=True)
    external_url = models.URLField(blank=True, default="")
    file_size = models.PositiveIntegerField(default=0)
    material_date = models.DateField(help_text="Data de referência para organização dos materiais")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-material_date", "-created_at"]
        verbose_name = "Material do Aluno"
        verbose_name_plural = "Materiais dos Alunos"

    def __str__(self):
        return f"{self.student.name} - {self.title}"


class TeacherMaterial(models.Model):
    """
    Biblioteca pessoal de materiais do professor (Arquivos).
    Independente de alunos. Pode ser compartilhado com um aluno via ação 'Enviar para aluno',
    que cria um StudentMaterial derivado.
    """

    TYPE_FILE = "file"
    TYPE_LINK = "link"
    TYPE_CHOICES = [
        (TYPE_FILE, "Arquivo"),
        (TYPE_LINK, "Link"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="teacher_materials",
        help_text="Professor dono deste material",
    )

    title = models.CharField(
        max_length=200,
        help_text="Nome/título do material exibido na biblioteca",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Descrição ou observação interna (não visível ao aluno)",
    )
    material_type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default=TYPE_FILE,
    )
    file = models.FileField(
        upload_to="teacher_materials/%Y/%m/",
        blank=True,
        null=True,
        help_text="Arquivo (preenchido quando material_type='file')",
    )
    external_url = models.URLField(
        blank=True,
        default="",
        help_text="URL externa (preenchida quando material_type='link')",
    )
    file_size = models.PositiveIntegerField(
        default=0,
        help_text="Tamanho do arquivo em bytes (0 para links)",
    )

    tags = models.CharField(
        max_length=300,
        blank=True,
        default="",
        help_text="Tags de organização separadas por vírgula (ex: gramática,B2,speaking)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Material do Professor"
        verbose_name_plural = "Materiais do Professor"

    def __str__(self):
        return f"{self.user.username} — {self.title}"

    def get_file_size_display(self):
        size = float(self.file_size)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class UserProfile(models.Model):
    """Perfil estendido do usuário"""
    PROFILE_TEACHER = "professor"
    PROFILE_PARTNER_TEACHER = "prof_parceiro"

    PROFILE_CHOICES = [
        (PROFILE_TEACHER, "Professor"),
        (PROFILE_PARTNER_TEACHER, "Prof. Parceiro"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    is_admin = models.BooleanField(default=False, help_text="Usuário administrador pode cadastrar outros usuários")
    user_profile = models.CharField(
        max_length=20,
        choices=PROFILE_CHOICES,
        default=PROFILE_TEACHER,
        help_text="Perfil do usuário no sistema"
    )
    partner_teachers = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='teachers',
        help_text="Professores parceiros vinculados (apenas para perfil Professor)"
    )
    
    # Campos adicionais do perfil
    cpf_cnpj = models.CharField(max_length=20, blank=True, help_text="CPF ou CNPJ")

    # Chave Pix do professor, usada nas mensagens de cobrança.
    #
    # Na prática a maioria recebe no próprio CPF ou CNPJ, e obrigar a digitar
    # o mesmo número duas vezes convida a erro de digitação num campo onde
    # errar significa dinheiro no lugar errado. Por isso a marca: ligada, a
    # cobrança usa o cpf_cnpj acima. Quem recebe noutra chave, telefone,
    # e-mail ou aleatória, desliga a marca e preenche pix_key.
    cpf_cnpj_is_pix = models.BooleanField(
        default=False,
        help_text="O CPF/CNPJ acima também é a chave Pix",
    )
    pix_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Chave Pix, quando for diferente do CPF/CNPJ",
    )

    phone = models.CharField(max_length=50, blank=True, help_text="Telefone/WhatsApp")
    cep = models.CharField(max_length=10, blank=True, help_text="CEP")
    address = models.CharField(max_length=255, blank=True, help_text="Endereço completo")
    city = models.CharField(max_length=100, blank=True, help_text="Cidade")
    state = models.CharField(max_length=2, blank=True, help_text="UF (Estado)")
    timezone = models.CharField(max_length=50, default="America/Sao_Paulo", help_text="Timezone")
    language = models.CharField(max_length=10, default="pt-BR", help_text="Idioma preferido")
    photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True, help_text="Foto do perfil")
    welcome_dismissed_forever = models.BooleanField(
        default=False,
        help_text="Se True, o popup de boas-vindas não é exibido novamente"
    )

    # Lembrete de fim de pacote de aulas. O padrão vale para todos os alunos
    # do professor; cada aluno pode ter o seu próprio limite
    # (Student.lesson_alert_threshold).
    lesson_alert_enabled = models.BooleanField(
        default=True,
        help_text="Avisar quando o pacote de aulas de um aluno estiver acabando",
    )
    lesson_alert_default = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Padrão: avisar quando faltarem N aulas para o pacote acabar",
    )
    subscription_exempt = models.BooleanField(
        default=False,
        help_text="Se True, o usuário não precisa de assinatura ativa para acessar o sistema (ex: admin, contas internas)"
    )
    # Agenda pública de agendamento (link único por professor)
    slug_publico = models.SlugField(
        max_length=80,
        unique=True,
        blank=True,
        null=True,
        help_text="Slug único para link público de agendamento (ex: ayla-barros). Só letras, números e hífens."
    )
    agenda_publica_ativa = models.BooleanField(
        default=False,
        help_text="Se True, a agenda pública está ativa e o link pode ser compartilhado"
    )
    public_availability = models.JSONField(
        default=dict,
        blank=True,
        help_text="Horários disponíveis por dia da semana. Formato: {1:[18:00,21:00], 2:[18:00,21:00], ...} (0=domingo, 6=sábado)"
    )
    public_booking_duration = models.PositiveSmallIntegerField(
        default=60,
        help_text="Duração da aula em minutos para agendamento público"
    )
    onboarding_24h_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data/hora em que o email de onboarding (24h pós-cadastro) foi enviado"
    )
    pending_subscription_recovery_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data/hora em que o email de recuperação (assinatura pendente) foi enviado"
    )
    trial_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fim do trial gratuito de 7 dias (sem cartão). Após essa data, o usuário precisa assinar."
    )
    trial_ending_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data em que o email de aviso (trial terminando em 2 dias) foi enviado"
    )

    # Campos de gestão interna (Admin Panel)
    admin_notes = models.TextField(
        blank=True,
        default='',
        help_text="Notas internas do admin sobre este usuário (não visível para o usuário)"
    )
    last_contacted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data/hora do último contato realizado pelo admin com este usuário"
    )
    last_retention_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data/hora do último e-mail de retenção enviado manualmente pelo admin"
    )
    last_retention_email_type = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Tipo do último e-mail de retenção enviado (trial_expiring, trial_expired, canceling)"
    )
    # Sign in with Google (JWT id_token) — telefone não vem no token; exigiria escopo + People API
    google_sub = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="ID estável da conta Google (claim sub)",
    )
    google_picture_url = models.URLField(
        max_length=2048,
        blank=True,
        default="",
        help_text="Foto de perfil (URL) enviada pelo Google",
    )
    google_hosted_domain = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Domínio Google Workspace (claim hd), se existir",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def chave_pix(self):
        """A chave Pix que vale para as cobranças deste professor.

        Um único lugar a decidir entre a marca no CPF/CNPJ e a chave própria,
        para a tela de cobrança, a mensagem e qualquer coisa futura darem
        sempre a mesma resposta. Devolve string vazia quando não há chave.
        """
        if self.cpf_cnpj_is_pix and (self.cpf_cnpj or "").strip():
            return self.cpf_cnpj.strip()
        return (self.pix_key or "").strip()

    def __str__(self):
        profile_display = dict(self.PROFILE_CHOICES).get(self.user_profile, self.user_profile)
        return f"{self.user.username} - {profile_display}"

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"


class Subscription(models.Model):
    """Assinatura do usuário no sistema - controle de billing"""
    
    # Tiers (níveis de plano)
    TIER_BASIC = "basic"
    TIER_PREMIUM = "premium"
    TIER_PLATINUM = "platinum"
    
    TIER_CHOICES = [
        (TIER_BASIC, "Basic"),
        (TIER_PREMIUM, "Premium"),
        (TIER_PLATINUM, "Platinum"),
    ]
    
    # Periodicidade (frequência de cobrança)
    PLAN_MONTHLY = "monthly"
    PLAN_SEMESTRAL = "semestral"
    PLAN_ANNUAL = "annual"
    
    PLAN_CHOICES = [
        (PLAN_MONTHLY, "Mensal"),
        (PLAN_SEMESTRAL, "Semestral"),
        (PLAN_ANNUAL, "Anual"),
    ]
    
    STATUS_ACTIVE = "active"
    STATUS_PENDING = "pending"
    STATUS_CANCELED = "canceled"
    STATUS_PAST_DUE = "past_due"
    STATUS_UNPAID = "unpaid"
    
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Ativa"),
        (STATUS_PENDING, "Pendente"),
        (STATUS_CANCELED, "Cancelada"),
        (STATUS_PAST_DUE, "Atrasada"),
        (STATUS_UNPAID, "Não paga"),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="subscription",
        help_text="Usuário da assinatura"
    )
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default=TIER_BASIC,
        help_text="Tier do plano (Basic, Premium, Platinum)"
    )
    plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        help_text="Periodicidade do plano (Mensal, Semestral, Anual)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        help_text="Status da assinatura"
    )
    
    # IDs do Stripe
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="ID do cliente no Stripe"
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text="ID da assinatura no Stripe"
    )
    
    # Datas importantes
    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Início do período atual"
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fim do período atual"
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="Cancelar ao fim do período"
    )
    cancel_scheduled_email_sent_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Data em que o email de cancelamento agendado foi enviado"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def is_active(self):
        """Retorna True se a assinatura está ativa"""
        return self.status == self.STATUS_ACTIVE
    
    def get_max_students(self):
        """Retorna o limite máximo de alunos para este tier"""
        if self.tier == self.TIER_BASIC:
            return 15
        return None  # Ilimitado para Premium e Platinum
    
    def get_max_partner_teachers(self):
        """Retorna o limite máximo de professores parceiros para este tier"""
        if self.tier == self.TIER_BASIC:
            return 0
        elif self.tier == self.TIER_PREMIUM:
            return 2
        return None  # Ilimitado para Platinum

    def get_arquivos_limits(self):
        """Retorna os limites de Arquivos para este tier."""
        limits = {
            self.TIER_BASIC: {
                "max_file_size": 10 * 1024 * 1024,
                "max_total_bytes": 100 * 1024 * 1024,
                "max_files": 50,
            },
            self.TIER_PREMIUM: {
                "max_file_size": 20 * 1024 * 1024,
                "max_total_bytes": 500 * 1024 * 1024,
                "max_files": 200,
            },
            self.TIER_PLATINUM: {
                "max_file_size": 50 * 1024 * 1024,
                "max_total_bytes": 2 * 1024 * 1024 * 1024,
                "max_files": None,
            },
        }
        return limits.get(self.tier, limits[self.TIER_BASIC])
    
    class Meta:
        verbose_name = "Assinatura"


class DayNote(models.Model):
    """Notas/observações do dia para o calendário"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="day_notes",
        help_text="Professor responsável pela nota"
    )
    date = models.DateField(help_text="Data da nota (YYYY-MM-DD)")
    text = models.TextField(blank=True, help_text="Texto da observação do dia")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['user', 'date']]
        ordering = ['-date']
        verbose_name = "Nota do Dia"
        verbose_name_plural = "Notas do Dia"

    def __str__(self):
        return f"{self.date} - {self.user.username}"
        verbose_name_plural = "Assinaturas"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_tier_display()} {self.get_plan_display()} - {self.get_status_display()}"
    
    @property
    def is_active(self):
        """Retorna True se a assinatura está ativa"""
        return self.status == self.STATUS_ACTIVE


class StripeEvent(models.Model):
    """Registro de eventos do Stripe para idempotência de webhooks"""
    
    event_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="ID único do evento no Stripe"
    )
    event_type = models.CharField(
        max_length=100,
        help_text="Tipo do evento (ex: invoice.paid, customer.subscription.deleted)"
    )
    processed = models.BooleanField(
        default=False,
        help_text="Se o evento já foi processado"
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando o evento foi processado"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Mensagem de erro se houver falha no processamento"
    )
    event_data = models.JSONField(
        default=dict,
        help_text="Dados completos do evento (para debug)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Evento Stripe"
        verbose_name_plural = "Eventos Stripe"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_id"]),
            models.Index(fields=["event_type", "processed"]),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.event_id} - {'Processado' if self.processed else 'Pendente'}"


class SupportTicket(models.Model):
    """Tickets de suporte enviados pelos usuários"""
    
    CATEGORY_BUG = "bug"
    CATEGORY_UX = "ux"
    CATEGORY_PAYMENT = "payment"
    CATEGORY_FEATURE = "feature"
    CATEGORY_OTHER = "other"
    
    CATEGORY_CHOICES = [
        (CATEGORY_BUG, "Bug / Erro"),
        (CATEGORY_UX, "UX / Layout"),
        (CATEGORY_PAYMENT, "Pagamento / Assinatura"),
        (CATEGORY_FEATURE, "Sugestão"),
        (CATEGORY_OTHER, "Outro"),
    ]
    
    IMPACT_LOW = "low"
    IMPACT_MEDIUM = "medium"
    IMPACT_HIGH = "high"
    
    IMPACT_CHOICES = [
        (IMPACT_LOW, "Baixo (incômodo)"),
        (IMPACT_MEDIUM, "Médio (atrapalha)"),
        (IMPACT_HIGH, "Alto (bloqueia uso)"),
    ]
    
    ticket_id = models.CharField(
        max_length=20,
        unique=True,
        help_text="ID único do ticket (gerado automaticamente)"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="support_tickets",
        help_text="Usuário que criou o ticket"
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        help_text="Categoria do problema"
    )
    impact = models.CharField(
        max_length=20,
        choices=IMPACT_CHOICES,
        help_text="Impacto do problema"
    )
    title = models.CharField(
        max_length=80,
        help_text="Título curto do problema"
    )
    description = models.TextField(
        max_length=2000,
        help_text="Descrição detalhada do problema"
    )
    
    # Contexto da página
    page = models.CharField(
        max_length=255,
        blank=True,
        help_text="Página onde o problema foi reportado"
    )
    query = models.CharField(
        max_length=500,
        blank=True,
        help_text="Query string da URL"
    )
    url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL completa onde o problema foi reportado"
    )
    
    # Timestamps
    created_at_local = models.CharField(
        max_length=50,
        blank=True,
        help_text="Timestamp local do cliente (string)"
    )
    timezone = models.CharField(
        max_length=100,
        blank=True,
        help_text="Timezone do cliente"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp do servidor (timezone aware)"
    )
    
    # Status do ticket (aberto / concluído)
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Aberto"),
        (STATUS_CLOSED, "Concluído"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        help_text="Status do ticket"
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data em que o ticket foi marcado como concluído"
    )

    # Status do email
    email_sent = models.BooleanField(
        default=False,
        help_text="Se o email foi enviado com sucesso"
    )
    email_error = models.TextField(
        blank=True,
        help_text="Erro ao enviar email (se houver)"
    )

    class Meta:
        verbose_name = "Ticket de Suporte"
        verbose_name_plural = "Tickets de Suporte"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ticket_id"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["category", "impact"]),
        ]
    
    def __str__(self):
        return f"#{self.ticket_id} - {self.title} - {self.user.username}"


class PublicBookingRequest(models.Model):
    """Solicitação de agendamento via link público (não expõe dados sensíveis)"""
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_CONFIRMED, "Confirmada"),
        (STATUS_CANCELLED, "Cancelada"),
    ]

    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="public_booking_requests",
        help_text="Professor que receberá a solicitação"
    )
    requested_date = models.DateField(help_text="Data solicitada")
    requested_time = models.TimeField(help_text="Horário solicitado")
    duration_minutes = models.PositiveSmallIntegerField(default=60)

    # Dados do aluno (apenas para contato - não cria aluno automaticamente)
    student_name = models.CharField(max_length=255)
    student_whatsapp = models.CharField(max_length=30)
    student_email = models.EmailField()
    subject = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Solicitação de agendamento público"
        verbose_name_plural = "Solicitações de agendamento público"

    def __str__(self):
        return f"{self.student_name} → {self.teacher.get_full_name()} {self.requested_date} {self.requested_time}"


class RetentionEmailLog(models.Model):
    """Histórico de e-mails de retenção enviados pelo admin manualmente."""

    EMAIL_TYPE_CHOICES = [
        ('trial_expiring', '⏰ Trial expirando'),
        ('trial_expired',  '🔴 Trial vencido'),
        ('canceling',      '⚠️ Cancelamento'),
    ]

    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='retention_email_logs',
    )
    email_type = models.CharField(max_length=50, choices=EMAIL_TYPE_CHOICES)
    subject = models.CharField(max_length=255, blank=True)
    personal_note = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='retention_emails_sent',
    )

    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'Log de e-mail de retenção'
        verbose_name_plural = 'Logs de e-mails de retenção'

    def __str__(self):
        return f"{self.user.email} — {self.email_type} em {self.sent_at:%d/%m/%Y %H:%M}"


class FeatureEmailCampaign(models.Model):
    """
    Campanha de email de anúncio de funcionalidade (enviada pelo admin).

    MVP: apenas criação/preview/envio; edição de rascunho pode vir depois.
    """

    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_SENT, "Enviado"),
    ]

    title = models.CharField(max_length=255, help_text="Título interno da campanha (não aparece no email)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    subject = models.CharField(max_length=255, help_text="Assunto do email")
    preview_text = models.CharField(max_length=200, blank=True, help_text="Pre-header (texto oculto)")
    feature_name = models.CharField(max_length=100, help_text="Nome da funcionalidade")

    # Lista de strings: cada item vira um parágrafo no corpo.
    body_json = models.JSONField(default=list, help_text="Lista de strings (parágrafos).")

    cta_label = models.CharField(max_length=100, help_text="Texto do botão CTA")
    cta_url = models.URLField(help_text="URL do botão CTA")

    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feature_campaigns_sent",
    )
    recipient_count = models.PositiveIntegerField(default=0, help_text="Quantidade de destinatários no envio.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Campanha de email de funcionalidade"
        verbose_name_plural = "Campanhas de email de funcionalidade"

    def __str__(self) -> str:
        return f"{self.title} — {self.get_status_display()}"


class FeatureEmailLog(models.Model):
    """Log individual por destinatário (1 por user/campaign)."""

    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SENT, "Enviado"),
        (STATUS_FAILED, "Falhou"),
    ]

    campaign = models.ForeignKey(
        FeatureEmailCampaign,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="feature_email_logs")

    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SENT)
    error_message = models.TextField(blank=True, help_text="Erro em caso de falha no envio.")

    class Meta:
        ordering = ["-sent_at"]
        verbose_name = "Log de email de funcionalidade"
        verbose_name_plural = "Logs de email de funcionalidade"
        unique_together = [("campaign", "user")]

    def __str__(self) -> str:
        return f"{self.campaign.title} → {self.user.email} [{self.status}]"


# ===========================================================================
# WhatsApp Business (Cloud API)
# ===========================================================================
#
# O canal é da conta do professor dono (a escola), não do sistema. Um número
# atende vários professores parceiros, e cada conversa tem um responsável,
# herdado de Student.assigned_teacher. O parceiro enxerga só as conversas dos
# alunos dele; o dono enxerga tudo.
#
# A regra de envio vive em core/whatsapp.py. Aqui ficam só o estado e as
# perguntas que o resto do sistema faz ("a janela está aberta?", "esta pessoa
# consentiu?").


class WhatsAppAccount(models.Model):
    """Número WhatsApp Business conectado por um professor dono."""

    STATUS_PENDING = "pending"
    STATUS_CONNECTED = "connected"
    STATUS_ERROR = "error"
    STATUS_DISCONNECTED = "disconnected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Aguardando conexão"),
        (STATUS_CONNECTED, "Conectado"),
        (STATUS_ERROR, "Com erro"),
        (STATUS_DISCONNECTED, "Desconectado"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="whatsapp_account",
        help_text="Professor dono da conta (a escola). Parceiros usam o número dele."
    )

    # Identificadores da Meta
    waba_id = models.CharField(
        max_length=64, blank=True,
        help_text="ID da WhatsApp Business Account do cliente"
    )
    phone_number_id = models.CharField(
        max_length=64, unique=True,
        help_text="ID do número na Cloud API. É por aqui que o webhook acha a conta."
    )
    business_id = models.CharField(
        max_length=64, blank=True,
        help_text="ID do Business Manager do cliente"
    )

    display_phone_number = models.CharField(
        max_length=32, blank=True,
        help_text="Número como a Meta devolve, ex.: +55 41 98836-9627"
    )
    verified_name = models.CharField(
        max_length=255, blank=True,
        help_text="Nome de exibição aprovado pela Meta"
    )

    # Token de acesso, cifrado em repouso. Nunca ler este campo direto:
    # usar get_access_token() / set_access_token().
    access_token_encrypted = models.TextField(
        blank=True,
        help_text="Token de acesso cifrado. Não expor em API nem em log."
    )

    is_coexistence = models.BooleanField(
        default=True,
        help_text="Número também ativo no aplicativo do celular. Mensagens enviadas "
                  "por lá chegam como echo e não passam pela janela de 24h."
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Interruptor por conta. Desligado, o sistema não envia nada."
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    quality_rating = models.CharField(
        max_length=20, blank=True,
        help_text="GREEN, YELLOW ou RED. Cai quando os destinatários denunciam."
    )
    messaging_limit = models.CharField(
        max_length=32, blank=True,
        help_text="Tier de envio da Meta, ex.: TIER_1K"
    )

    last_error = models.TextField(blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    connected_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conta WhatsApp"
        verbose_name_plural = "Contas WhatsApp"

    def __str__(self) -> str:
        return f"{self.verified_name or self.display_phone_number or self.phone_number_id}"

    def set_access_token(self, plaintext: str) -> None:
        from core.whatsapp import encrypt_secret
        self.access_token_encrypted = encrypt_secret(plaintext)

    def get_access_token(self) -> str:
        from core.whatsapp import decrypt_secret
        return decrypt_secret(self.access_token_encrypted)

    def get_client(self):
        """Cliente da Cloud API já configurado para esta conta."""
        from core.whatsapp import CloudAPIClient
        return CloudAPIClient(
            phone_number_id=self.phone_number_id,
            access_token=self.get_access_token(),
            waba_id=self.waba_id,
        )

    @property
    def can_send(self) -> bool:
        from core.whatsapp import is_enabled
        return bool(
            is_enabled()
            and self.is_active
            and self.status == self.STATUS_CONNECTED
            and self.access_token_encrypted
        )

    def register_error(self, message: str) -> None:
        """Guarda a última falha sem derrubar a conta por um erro isolado."""
        self.last_error = (message or "")[:2000]
        self.last_error_at = timezone.now()
        self.save(update_fields=["last_error", "last_error_at", "updated_at"])


class WhatsAppContact(models.Model):
    """
    Um número que conversa com a escola.

    Nasce da primeira mensagem recebida, mesmo sem aluno ligado: é comum o
    responsável escrever antes de a professora cadastrar o filho. O vínculo com
    Student pode ser feito depois, na caixa de entrada.
    """

    RELATIONSHIP_UNKNOWN = "unknown"
    RELATIONSHIP_STUDENT = "student"
    RELATIONSHIP_GUARDIAN = "guardian"
    RELATIONSHIP_LEAD = "lead"
    RELATIONSHIP_OTHER = "other"

    RELATIONSHIP_CHOICES = [
        (RELATIONSHIP_UNKNOWN, "Não identificado"),
        (RELATIONSHIP_STUDENT, "Aluno"),
        (RELATIONSHIP_GUARDIAN, "Responsável"),
        (RELATIONSHIP_LEAD, "Interessado"),
        (RELATIONSHIP_OTHER, "Outro"),
    ]

    # Consentimento para receber mensagem iniciada pela escola (template).
    # Sem isto, disparo em massa vira denúncia e derruba a qualidade do número.
    OPT_IN_PENDING = "pending"
    OPT_IN_GRANTED = "granted"
    OPT_IN_REVOKED = "revoked"

    OPT_IN_CHOICES = [
        (OPT_IN_PENDING, "Não perguntado"),
        (OPT_IN_GRANTED, "Aceitou receber"),
        (OPT_IN_REVOKED, "Pediu para parar"),
    ]

    account = models.ForeignKey(
        WhatsAppAccount, on_delete=models.CASCADE, related_name="contacts"
    )
    wa_id = models.CharField(
        max_length=32,
        help_text="Identificador da Meta, E.164 sem '+'. No Brasil pode vir sem o nono dígito."
    )
    phone_e164 = models.CharField(
        max_length=32, blank=True,
        help_text="Número normalizado com o nono dígito, para casar com o cadastro."
    )
    profile_name = models.CharField(
        max_length=255, blank=True,
        help_text="Nome que a pessoa usa no WhatsApp"
    )

    student = models.ForeignKey(
        'Student', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="whatsapp_contacts",
        help_text="Aluno ligado a este número. Um aluno pode ter mãe e pai separados."
    )
    relationship = models.CharField(
        max_length=20, choices=RELATIONSHIP_CHOICES, default=RELATIONSHIP_UNKNOWN
    )

    opt_in_status = models.CharField(
        max_length=20, choices=OPT_IN_CHOICES, default=OPT_IN_PENDING
    )
    opt_in_at = models.DateTimeField(null=True, blank=True)
    opt_in_source = models.CharField(
        max_length=100, blank=True,
        help_text="Onde o consentimento foi dado: contrato, matrícula, resposta no WhatsApp..."
    )

    is_blocked = models.BooleanField(
        default=False,
        help_text="Não enviar nada para este número, em nenhuma circunstância."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("account", "wa_id")]
        indexes = [
            models.Index(fields=["account", "phone_e164"]),
            models.Index(fields=["student"]),
        ]
        verbose_name = "Contato WhatsApp"
        verbose_name_plural = "Contatos WhatsApp"

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        if self.student_id:
            return self.student.name
        return self.profile_name or self.formatted_phone

    @property
    def formatted_phone(self) -> str:
        from core.whatsapp import format_phone_br
        return format_phone_br(self.phone_e164 or self.wa_id)

    @property
    def can_receive_template(self) -> bool:
        """Mensagem iniciada pela escola exige consentimento registrado."""
        return not self.is_blocked and self.opt_in_status == self.OPT_IN_GRANTED

    def grant_opt_in(self, source: str) -> None:
        self.opt_in_status = self.OPT_IN_GRANTED
        self.opt_in_at = timezone.now()
        self.opt_in_source = source[:100]
        self.save(update_fields=["opt_in_status", "opt_in_at", "opt_in_source", "updated_at"])

    def revoke_opt_in(self, source: str = "pedido do contato") -> None:
        self.opt_in_status = self.OPT_IN_REVOKED
        self.opt_in_source = source[:100]
        self.save(update_fields=["opt_in_status", "opt_in_source", "updated_at"])


class WhatsAppConversation(models.Model):
    """
    A thread com um contato.

    Guarda o que a caixa de entrada precisa responder rápido sem varrer as
    mensagens: quem atende, quando a janela fecha, quantas não lidas.
    """

    account = models.ForeignKey(
        WhatsAppAccount, on_delete=models.CASCADE, related_name="conversations"
    )
    contact = models.OneToOneField(
        WhatsAppContact, on_delete=models.CASCADE, related_name="conversation"
    )

    assigned_teacher = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="whatsapp_conversations",
        help_text="Professor responsável. Herdado de Student.assigned_teacher, "
                  "com o dono da conta como padrão."
    )

    last_inbound_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Última mensagem recebida. É o que abre a janela de 24h."
    )
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_preview = models.CharField(max_length=200, blank=True)

    unread_count = models.PositiveIntegerField(default=0)
    is_archived = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at"]
        indexes = [
            models.Index(fields=["account", "-last_message_at"]),
            models.Index(fields=["assigned_teacher", "-last_message_at"]),
        ]
        verbose_name = "Conversa WhatsApp"
        verbose_name_plural = "Conversas WhatsApp"

    def __str__(self) -> str:
        return f"Conversa com {self.contact.display_name}"

    @property
    def window_is_open(self) -> bool:
        """Dá para enviar texto livre pela API? Fora disso, só template."""
        from core.whatsapp import window_is_open
        return window_is_open(self.last_inbound_at)

    @property
    def window_expires_at(self):
        from core.whatsapp import window_expires_at
        return window_expires_at(self.last_inbound_at)

    def resolve_assigned_teacher(self) -> User:
        """
        Decide quem atende: o professor do aluno, ou o dono da conta.

        Chamado quando o contato é ligado a um aluno, e quando o aluno troca
        de professor parceiro.
        """
        student = self.contact.student
        if student and student.assigned_teacher_id:
            return student.assigned_teacher
        return self.account.user

    def visible_to(self, user: User) -> bool:
        """
        Regra de visibilidade da caixa de entrada.

        O dono da conta vê tudo, porque é o número dele e a responsabilidade é
        dele. O parceiro vê só o que foi atribuído a ele.
        """
        if user.id == self.account.user_id:
            return True
        return self.assigned_teacher_id == user.id


class WhatsAppTemplate(models.Model):
    """
    Template aprovado pela Meta, ligado ao uso que o sistema faz dele.

    O `purpose` é o que permite o código pedir "o template de cobrança em
    atraso" sem saber o nome que a Meta aprovou, que muda por conta.
    """

    PURPOSE_BILLING_FRIENDLY = "billing_friendly"
    PURPOSE_BILLING_DUE_TODAY = "billing_due_today"
    PURPOSE_BILLING_OVERDUE = "billing_overdue"
    PURPOSE_BILLING_THANK_YOU = "billing_thank_you"
    PURPOSE_LESSON_REMINDER = "lesson_reminder"
    PURPOSE_LESSON_CANCELLED = "lesson_cancelled"
    PURPOSE_TASK_ASSIGNED = "task_assigned"
    PURPOSE_PACKAGE_ENDING = "package_ending"
    PURPOSE_OPT_IN_REQUEST = "opt_in_request"
    PURPOSE_OTHER = "other"

    PURPOSE_CHOICES = [
        (PURPOSE_BILLING_FRIENDLY, "Cobrança: lembrete amigável"),
        (PURPOSE_BILLING_DUE_TODAY, "Cobrança: vence hoje"),
        (PURPOSE_BILLING_OVERDUE, "Cobrança: em atraso"),
        (PURPOSE_BILLING_THANK_YOU, "Cobrança: agradecimento"),
        (PURPOSE_LESSON_REMINDER, "Lembrete de aula"),
        (PURPOSE_LESSON_CANCELLED, "Aula cancelada"),
        (PURPOSE_TASK_ASSIGNED, "Tarefa enviada"),
        (PURPOSE_PACKAGE_ENDING, "Pacote de aulas acabando"),
        (PURPOSE_OPT_IN_REQUEST, "Pedido de autorização para enviar mensagens"),
        (PURPOSE_OTHER, "Outro"),
    ]

    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_PAUSED = "PAUSED"
    STATUS_DISABLED = "DISABLED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Em análise"),
        (STATUS_APPROVED, "Aprovado"),
        (STATUS_REJECTED, "Reprovado"),
        (STATUS_PAUSED, "Pausado pela Meta"),
        (STATUS_DISABLED, "Desativado"),
    ]

    CATEGORY_UTILITY = "UTILITY"
    CATEGORY_MARKETING = "MARKETING"
    CATEGORY_AUTHENTICATION = "AUTHENTICATION"

    CATEGORY_CHOICES = [
        (CATEGORY_UTILITY, "Utilidade"),
        (CATEGORY_MARKETING, "Marketing"),
        (CATEGORY_AUTHENTICATION, "Autenticação"),
    ]

    account = models.ForeignKey(
        WhatsAppAccount, on_delete=models.CASCADE, related_name="templates"
    )
    name = models.CharField(max_length=255, help_text="Nome exato aprovado na Meta")
    language = models.CharField(max_length=10, default="pt_BR")
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_UTILITY
    )
    purpose = models.CharField(
        max_length=40, choices=PURPOSE_CHOICES, default=PURPOSE_OTHER
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    body_text = models.TextField(
        blank=True, help_text="Corpo aprovado, com as chaves {{1}}, {{2}}..."
    )
    variable_hints = models.JSONField(
        default=list, blank=True,
        help_text="Descrição de cada variável, na ordem. Ex.: ['nome', 'valor', 'vencimento']"
    )

    rejected_reason = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("account", "name", "language")]
        verbose_name = "Template WhatsApp"
        verbose_name_plural = "Templates WhatsApp"

    def __str__(self) -> str:
        return f"{self.name} [{self.status}]"

    @property
    def is_usable(self) -> bool:
        return self.status == self.STATUS_APPROVED


class WhatsAppMessage(models.Model):
    """
    Uma mensagem, recebida ou enviada.

    Em coexistence, mensagem de saída pode ter nascido no aplicativo do celular
    (origin=app) em vez de no sistema (origin=api). As duas entram aqui, senão
    o histórico fica pela metade e a professora não confia na caixa de entrada.
    """

    DIRECTION_INBOUND = "in"
    DIRECTION_OUTBOUND = "out"

    DIRECTION_CHOICES = [
        (DIRECTION_INBOUND, "Recebida"),
        (DIRECTION_OUTBOUND, "Enviada"),
    ]

    ORIGIN_API = "api"
    ORIGIN_APP = "app"
    ORIGIN_CONTACT = "contact"

    ORIGIN_CHOICES = [
        (ORIGIN_API, "Enviada pelo sistema"),
        (ORIGIN_APP, "Enviada pelo aplicativo do celular"),
        (ORIGIN_CONTACT, "Enviada pelo contato"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_DELIVERED = "delivered"
    STATUS_READ = "read"
    STATUS_FAILED = "failed"
    STATUS_RECEIVED = "received"

    STATUS_CHOICES = [
        (STATUS_QUEUED, "Na fila"),
        (STATUS_SENT, "Enviada"),
        (STATUS_DELIVERED, "Entregue"),
        (STATUS_READ, "Lida"),
        (STATUS_FAILED, "Falhou"),
        (STATUS_RECEIVED, "Recebida"),
    ]

    conversation = models.ForeignKey(
        WhatsAppConversation, on_delete=models.CASCADE, related_name="messages"
    )
    wamid = models.CharField(
        max_length=128, unique=True,
        help_text="ID da mensagem na Meta. Garante idempotência do webhook."
    )

    direction = models.CharField(max_length=4, choices=DIRECTION_CHOICES)
    origin = models.CharField(max_length=10, choices=ORIGIN_CHOICES)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED
    )

    message_type = models.CharField(
        max_length=30, default="text",
        help_text="text, image, audio, document, template..."
    )
    body = models.TextField(blank=True)

    media_id = models.CharField(max_length=128, blank=True)
    media_mime = models.CharField(max_length=100, blank=True)
    media_filename = models.CharField(max_length=255, blank=True)
    media_file = models.FileField(
        upload_to="whatsapp_media/%Y/%m/", blank=True, null=True,
        help_text="Cópia local. A URL da Meta expira e o anexo se perderia."
    )

    template = models.ForeignKey(
        WhatsAppTemplate, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="messages"
    )
    reply_to_wamid = models.CharField(max_length=128, blank=True)

    sent_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="whatsapp_messages_sent",
        help_text="Quem disparou pelo sistema. Vazio em echo do aplicativo."
    )

    # Rastro para o resto do sistema: de qual cobrança ou aula esta mensagem
    # saiu. Permite a ficha do aluno mostrar "cobrança enviada e lida".
    billing_log = models.ForeignKey(
        'BillingLog', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="whatsapp_messages"
    )
    lesson = models.ForeignKey(
        'Lesson', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="whatsapp_messages"
    )

    error_code = models.CharField(max_length=20, blank=True)
    error_message = models.TextField(blank=True)

    timestamp = models.DateTimeField(help_text="Hora da mensagem segundo a Meta")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["conversation", "timestamp"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "Mensagem WhatsApp"
        verbose_name_plural = "Mensagens WhatsApp"

    def __str__(self) -> str:
        arrow = "←" if self.direction == self.DIRECTION_INBOUND else "→"
        return f"{arrow} {(self.body or self.message_type)[:50]}"

    @property
    def is_from_app(self) -> bool:
        """Enviada pela professora no celular, não pelo sistema."""
        return self.origin == self.ORIGIN_APP


class WhatsAppWebhookEvent(models.Model):
    """
    Registro cru de cada webhook, para idempotência e para depurar.

    A Meta reentrega o mesmo evento quando não recebe 200 rápido. Sem esta
    tabela, uma lentidão do banco vira mensagem duplicada na conversa.
    """

    event_key = models.CharField(
        max_length=64, unique=True,
        help_text="Hash do conteúdo do evento. Ver whatsapp.webhook_event_key."
    )
    account = models.ForeignKey(
        WhatsAppAccount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="webhook_events"
    )
    payload = models.JSONField(default=dict)

    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [models.Index(fields=["-received_at"])]
        verbose_name = "Evento de webhook WhatsApp"
        verbose_name_plural = "Eventos de webhook WhatsApp"

    def __str__(self) -> str:
        state = "ok" if self.processed else "pendente"
        return f"{self.event_key[:12]} [{state}]"


# ══════════════════════════════════════════════════════════════════════════
# BLOG
#
# Conteúdo de topo de funil: o professor chega pelo Google procurando "quanto
# cobrar por aula particular", lê, e encontra o EDUCAflowOne no meio do texto.
# Por isso o artigo é registro de banco e não template: quem escreve publica
# pelo /admin/, sem deploy, e a data de publicação é o que o Google lê.
#
# O corpo é escrito em Markdown e renderizado por core/blog_markdown.py.
# ══════════════════════════════════════════════════════════════════════════


class BlogCategory(models.Model):
    """Editoria do blog. Existe para o leitor filtrar e para a URL fazer sentido."""

    name = models.CharField(max_length=60, unique=True, verbose_name="Nome")
    slug = models.SlugField(max_length=80, unique=True)
    description = models.CharField(
        max_length=220, blank=True,
        help_text="Uma linha, aparece no topo da página da categoria."
    )
    order = models.PositiveSmallIntegerField(
        default=0, help_text="Menor número aparece primeiro no menu do blog."
    )

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Categoria do blog"
        verbose_name_plural = "Categorias do blog"

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return f"/blog/categoria/{self.slug}/"


class BlogPostQuerySet(models.QuerySet):
    def published(self):
        """
        Publicado é status publicado E data já vencida: agendar um artigo é só
        marcar publicado com data futura.
        """
        return self.filter(
            status=BlogPost.STATUS_PUBLISHED,
            published_at__lte=timezone.now(),
        )

    def scheduled(self):
        """
        A fila. Artigos prontos, marcados como publicados, esperando a data.

        Não existe tarefa periódica por trás disto: o artigo entra no ar porque
        a consulta de publicados passa a incluí-lo quando o relógio passa da
        data. Sem worker, sem cron, sem nada para falhar de madrugada.
        """
        return self.filter(
            status=BlogPost.STATUS_PUBLISHED,
            published_at__gt=timezone.now(),
        ).order_by("published_at")


class BlogPost(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_PUBLISHED, "Publicado"),
    ]

    title = models.CharField(
        max_length=160, verbose_name="Título",
        help_text="O que o Google mostra. Até 60 caracteres aparece inteiro na busca."
    )
    slug = models.SlugField(
        max_length=180, unique=True, blank=True,
        help_text="Endereço do artigo. Deixe vazio para gerar do título. "
                  "Depois de publicado, mudar aqui quebra os links que já circulam."
    )
    dek = models.CharField(
        max_length=300, blank=True, verbose_name="Linha de apoio",
        help_text="A frase abaixo do título, no cartão da lista e nas redes."
    )
    category = models.ForeignKey(
        BlogCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="posts", verbose_name="Categoria"
    )
    content = models.TextField(
        verbose_name="Texto do artigo",
        help_text="Markdown. ## título de seção, ### subtítulo, - lista, "
                  "> destaque, **negrito**, [texto](link), | tabela |. "
                  "Escreva [[cta]] numa linha sozinha para escolher onde entra "
                  "o convite de cadastro; sem isso ele entra sozinho no meio."
    )

    cover = models.ImageField(
        upload_to="blog/capas/%Y/%m/", blank=True, null=True,
        verbose_name="Imagem de capa",
        help_text="Proporção 16:9, pelo menos 1200x630 para aparecer bem no WhatsApp."
    )
    cover_alt = models.CharField(
        max_length=180, blank=True, verbose_name="Descrição da capa",
        help_text="O que a imagem mostra, para quem usa leitor de tela."
    )

    author_name = models.CharField(max_length=90, default="Equipe EDUCAflowOne", verbose_name="Autor")
    author_role = models.CharField(max_length=120, blank=True, verbose_name="Cargo do autor")

    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True
    )
    featured = models.BooleanField(
        default=False, verbose_name="Destaque",
        help_text="O mais recente marcado assim abre a página do blog."
    )
    published_at = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name="Publicado em",
        help_text="Preenchido sozinho ao publicar. Data futura agenda o artigo."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # SEO. Ficam separados do título porque o título que converte no site e o
    # título que ganha clique na busca raramente são o mesmo.
    seo_title = models.CharField(
        max_length=70, blank=True, verbose_name="Título no Google",
        help_text="Vazio usa o título do artigo."
    )
    seo_description = models.CharField(
        max_length=180, blank=True, verbose_name="Descrição no Google",
        help_text="Vazio usa a linha de apoio, ou o primeiro parágrafo."
    )
    keywords = models.CharField(
        max_length=240, blank=True, verbose_name="Palavras-chave",
        help_text="Separadas por vírgula. Uso interno, para você lembrar do alvo."
    )

    # Convite de cadastro. Um artigo sobre cobrança converte melhor falando de
    # cobrança do que repetindo a mesma frase genérica de todos os outros.
    cta_title = models.CharField(max_length=120, blank=True, verbose_name="Título do convite")
    cta_text = models.CharField(max_length=300, blank=True, verbose_name="Texto do convite")
    cta_button = models.CharField(max_length=60, blank=True, verbose_name="Botão do convite")

    views = models.PositiveIntegerField(default=0, verbose_name="Leituras")
    reading_minutes = models.PositiveSmallIntegerField(default=1, verbose_name="Minutos de leitura")

    objects = BlogPostQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            # Nome explícito porque a migração deste modelo foi escrita à mão:
            # deixar o Django batizar sozinho faria os dois discordarem.
            models.Index(fields=["status", "-published_at"], name="blog_status_data_idx"),
        ]
        verbose_name = "Artigo do blog"
        verbose_name_plural = "Artigos do blog"

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        from .blog_markdown import reading_minutes as _minutos

        if not self.slug:
            base = slugify(self.title)[:170] or "artigo"
            slug, n = base, 2
            while BlogPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base[:170 - len(str(n)) - 1]}-{n}"
                n += 1
            self.slug = slug

        # Publicar sem data seria um artigo invisível: a listagem ordena por
        # data e a consulta de publicados exige data vencida.
        if self.status == self.STATUS_PUBLISHED and not self.published_at:
            self.published_at = timezone.now()

        self.reading_minutes = _minutos(self.content)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return f"/blog/{self.slug}/"

    @property
    def is_published(self) -> bool:
        return (
            self.status == self.STATUS_PUBLISHED
            and self.published_at is not None
            and self.published_at <= timezone.now()
        )

    @property
    def is_scheduled(self) -> bool:
        """Pronto e na fila, mas ainda não é a hora dele."""
        return (
            self.status == self.STATUS_PUBLISHED
            and self.published_at is not None
            and self.published_at > timezone.now()
        )

    @property
    def meta_title(self) -> str:
        return self.seo_title or self.title

    @property
    def meta_description(self) -> str:
        from .blog_markdown import plain_excerpt

        return self.seo_description or self.dek or plain_excerpt(self.content)

    @property
    def resumo(self) -> str:
        """O que vai no cartão da listagem."""
        from .blog_markdown import plain_excerpt

        return self.dek or plain_excerpt(self.content, 200)

    def render_html(self) -> str:
        """HTML do corpo, já com o ponto de inserção do convite de cadastro."""
        from .blog_markdown import auto_cta, render

        html, _ = render(self.content)
        return auto_cta(html)

    def sumario(self) -> list:
        """Lista de seções (h2) para o índice lateral. Só vale a pena com três ou mais."""
        from .blog_markdown import render

        _, toc = render(self.content)
        return toc if len(toc) >= 3 else []

    def relacionados(self, limite: int = 3):
        qs = BlogPost.objects.published().exclude(pk=self.pk)
        mesmos = list(qs.filter(category=self.category)[:limite]) if self.category_id else []
        if len(mesmos) < limite:
            faltam = limite - len(mesmos)
            ids = [p.pk for p in mesmos]
            mesmos += list(qs.exclude(pk__in=ids)[:faltam])
        return mesmos
