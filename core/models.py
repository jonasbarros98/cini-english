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
