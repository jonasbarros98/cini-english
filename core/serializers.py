from rest_framework import serializers
from .models import Student, Lesson, Task, Invoice, FinancialEntry


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            "id",
            "name",
            "guardians",
            "phone",
            "address",
            "plan_name",
            "lessons_total",
            "lessons_done",
            "pix_key",
            "active",
            "created_at",
            "updated_at",
        ]


class LessonSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = Lesson
        fields = [
            "id",
            "student",
            "student_name",
            "date",
            "time",
            "title",
            "info",
            "status",
            "created_at",
            "updated_at",
        ]


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "status",
            "tags",
            "date",
            "due_date",
            "notes",
            "created_at",
            "updated_at",
        ]

class InvoiceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "student",
            "student_name",
            "month",
            "due_date",
            "amount",
            "status",
            "notes",
        ]


class FinancialEntrySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = FinancialEntry
        fields = [
            "id",
            "student",
            "student_name",
            "description",
            "amount",
            "installments",
            "current_installment",
            "issue_date",
            "due_date",
            "payment_date",
            "status",
            "payment_method",
            "notes",
            "created_at",
            "updated_at",
        ]
