from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date

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
    plan_name = models.CharField(max_length=255, blank=True, help_text="Plano atual")
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
        help_text="Professor responsável pelo aluno"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "time"]

    def __str__(self) -> str:
        return f"{self.date} - {self.title}"


class Task(models.Model):
    STATUS_CHOICES = [
        ("todo", "A fazer"),
        ("doing", "Fazendo"),
        ("done", "Concluída"),
    ]

    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="todo",
    )

    # Opcional: continuar com tags, se quiser
    tags = models.CharField(
        max_length=255,
        blank=True,
        help_text="Tags separadas por vírgula, ex: Planejamento,Financeiro",
    )

    # >>> NOVOS CAMPOS PARA A TELA BONITA <<<
    # data “principal” da tarefa (quando ela acontece)
    date = models.DateField(null=True, blank=True)

    # data de vencimento / deadline
    due_date = models.DateField(null=True, blank=True)

    # descrição / observações
    notes = models.TextField(blank=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tasks",
        help_text="Usuário responsável pela tarefa"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        profile_display = dict(self.PROFILE_CHOICES).get(self.user_profile, self.user_profile)
        return f"{self.user.username} - {profile_display}"

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"