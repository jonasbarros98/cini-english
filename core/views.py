from datetime import datetime
from datetime import date
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Invoice, FinancialEntry
from .models import Student, Lesson, Task
from .serializers import StudentSerializer, LessonSerializer, TaskSerializer
from .serializers import InvoiceSerializer, FinancialEntrySerializer

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all().order_by("name")
    serializer_class = StudentSerializer


class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.select_related("student").all()
    serializer_class = LessonSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        # Filtros opcionais via query string:
        # /api/lessons/?date=2026-01-19
        # /api/lessons/?month=2026-01
        date_str = self.request.query_params.get("date")
        month_str = self.request.query_params.get("month")

        if date_str:
            # espera formato YYYY-MM-DD
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                qs = qs.filter(date=date_obj)
            except ValueError:
                pass

        if month_str:
            # espera formato YYYY-MM
            try:
                dt = datetime.strptime(month_str, "%Y-%m")
                qs = qs.filter(date__year=dt.year, date__month=dt.month)
            except ValueError:
                pass

        return qs.order_by("date", "time")

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        /api/lessons/stats/
        Retorna contagem de confirmadas/pendentes/canceladas.
        """
        base_qs = self.get_queryset()
        return Response({
            "confirmed": base_qs.filter(status="confirmed").count(),
            "pending": base_qs.filter(status="pending").count(),
            "canceled": base_qs.filter(status="canceled").count(),
        })


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all().order_by("-created_at")
    serializer_class = TaskSerializer

from django.views.generic import TemplateView

class DashboardView(TemplateView):
    template_name = "index.html"

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("student").all()
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        month_param = self.request.query_params.get("month")
        if month_param:
            # formato esperado: YYYY-MM
            try:
                year, month = map(int, month_param.split("-"))
                start = date(year, month, 1)
                if month == 12:
                    end = date(year + 1, 1, 1)
                else:
                    end = date(year, month + 1, 1)
                qs = qs.filter(month__gte=start, month__lt=end)
            except ValueError:
                pass
        return qs


class FinancialEntryViewSet(viewsets.ModelViewSet):
    queryset = FinancialEntry.objects.select_related("student").all()
    serializer_class = FinancialEntrySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Filtro por mês - mostra lançamentos com vencimento OU lançamento no mês
        month_param = self.request.query_params.get("month")
        if month_param:
            try:
                year, month = map(int, month_param.split("-"))
                # Mostra lançamentos que têm vencimento OU lançamento no mês especificado
                qs = qs.filter(
                    Q(due_date__year=year, due_date__month=month) |
                    Q(issue_date__year=year, issue_date__month=month)
                )
            except ValueError:
                pass
        # Filtro por status
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        # Filtro por aluno
        student_param = self.request.query_params.get("student")
        if student_param:
            qs = qs.filter(student_id=student_param)
        return qs