from django.db import models
from datetime import date

class Student(models.Model):
    name = models.CharField(max_length=255)
    guardians = models.CharField(
        max_length=255,
        help_text="Pai/mãe ou 'Responsável próprio'", blank=True
    )
    phone = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    plan_name = models.CharField(max_length=255, blank=True)
    lessons_total = models.PositiveSmallIntegerField(default=0)
    lessons_done = models.PositiveSmallIntegerField(default=0)
    pix_key = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)

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
    """Lançamento financeiro a receber de alunos"""
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

    PAYMENT_METHOD_CHOICES = [
        ("pix", "PIX"),
        ("cash", "Dinheiro"),
        ("card", "Cartão"),
        ("transfer", "Transferência"),
        ("other", "Outro"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="financial_entries"
    )
    description = models.CharField(max_length=255, help_text="Descrição do lançamento")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Valor total")
    installments = models.PositiveSmallIntegerField(default=1, help_text="Número de parcelas")
    current_installment = models.PositiveSmallIntegerField(default=1, help_text="Parcela atual")
    
    issue_date = models.DateField(help_text="Data de lançamento")
    due_date = models.DateField(help_text="Data de vencimento")
    payment_date = models.DateField(null=True, blank=True, help_text="Data do pagamento")
    
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default="pix", blank=True
    )
    notes = models.TextField(blank=True, help_text="Observações")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-due_date", "student__name"]
        verbose_name = "Lançamento Financeiro"
        verbose_name_plural = "Lançamentos Financeiros"

    def __str__(self):
        return f"{self.student.name} - {self.description} - {self.amount}"