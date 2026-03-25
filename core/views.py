from datetime import datetime, date, timedelta
from calendar import monthrange
from django.utils import timezone
from django.db import IntegrityError
from django.db.models import Q, Sum, Count, Max
from decimal import Decimal
from django.conf import settings
from django.urls import reverse
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.views.generic import TemplateView, View
from django.shortcuts import redirect, render, get_object_or_404
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
import stripe
import base64
import json
import os
import re
import uuid
import threading
from urllib import request as urllib_request
from .models import Invoice, FinancialEntry, UserProfile, LessonPlan, LessonPlanAttachment, BillingLog
from .models import Student, Lesson, Task, StudentHomework, StudentHomeworkMessage, StudentHomeworkMessageRead, Subscription, StripeEvent, DayNote, SupportTicket, PublicBookingRequest, StudentShareToken, StudentMaterial
from .serializers import StudentSerializer, LessonSerializer, TaskSerializer, StudentHomeworkSerializer
from .serializers import InvoiceSerializer, FinancialEntrySerializer, UserSerializer, LessonPlanSerializer, LessonPlanAttachmentSerializer, BillingLogSerializer, ProfileSerializer

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related("user", "assigned_teacher").all().order_by("name")
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # Suporta FormData e JSON
    
    def list(self, request, *args, **kwargs):
        """Lista alunos com header anti-cache para evitar lista desatualizada após criar/editar."""
        response = super().list(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    def get_queryset(self):
        qs = super().get_queryset()
        
        try:
            is_admin = self.request.user.profile.is_admin
            user_profile = self.request.user.profile.user_profile
        except UserProfile.DoesNotExist:
            is_admin = False
            user_profile = None
        
        if is_admin:
            return qs
        
        if user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
            # Prof. Parceiro: apenas alunos ATRIBUÍDOS a ele (assigned_teacher). Alunos sem professor ou com prof. principal não aparecem.
            qs = qs.filter(user__profile__partner_teachers=self.request.user.profile).filter(assigned_teacher=self.request.user)
        elif user_profile == UserProfile.PROFILE_TEACHER:
            # Prof. dono da conta: apenas alunos que ele cadastrou (user=ele)
            qs = qs.filter(user=self.request.user)
        else:
            qs = qs.filter(user=self.request.user)
        
        return qs
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def _is_partner_teacher(self):
        try:
            return self.request.user.profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
        except UserProfile.DoesNotExist:
            return False
    
    def perform_create(self, serializer):
        if self._is_partner_teacher():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor dono da conta pode cadastrar alunos.")
        # Verificar limite de alunos do plano (trial: sem limite)
        user = self.request.user
        if not _user_is_in_trial(user):
            try:
                subscription = user.subscription
                _sync_subscription_from_stripe(subscription)
                subscription.refresh_from_db()
                if subscription.is_active:
                    max_students = subscription.get_max_students()
                    if max_students is not None:
                        current_count = Student.objects.filter(user=user, status=Student.STATUS_ACTIVE).count()
                        if current_count >= max_students:
                            from rest_framework.exceptions import PermissionDenied
                            raise PermissionDenied(
                                f"Limite de {max_students} alunos atingido no plano {subscription.get_tier_display()}. "
                                f"Faça upgrade para Premium ou Platinum para alunos ilimitados."
                            )
            except Subscription.DoesNotExist:
                pass
        # assigned_teacher pode vir em validated_data; validar que é parceiro do dono
        serializer.save(user=user)
    
    def _is_admin(self):
        try:
            return self.request.user.profile.is_admin
        except UserProfile.DoesNotExist:
            return False

    def perform_update(self, serializer):
        if self._is_partner_teacher():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor dono da conta pode editar alunos.")
        instance = self.get_object()
        if not self._is_admin() and instance.user_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Você não pode editar este aluno.")
        serializer.save()
    
    def perform_destroy(self, instance):
        if self._is_partner_teacher():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor dono da conta pode excluir alunos.")
        if instance.user_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Você não pode excluir este aluno.")
        instance.delete()
    
    def create(self, request, *args, **kwargs):
        if self._is_partner_teacher():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor dono da conta pode cadastrar alunos.")
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        if self._is_partner_teacher():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor dono da conta pode editar alunos.")
        instance = self.get_object()
        if not self._is_admin() and instance.user_id != request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Você não pode editar este aluno.")
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        if self._is_partner_teacher():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor dono da conta pode excluir alunos.")
        instance = self.get_object()
        if not self._is_admin() and instance.user_id != request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Você não pode excluir este aluno.")
        # Impedir exclusão se houver qualquer lançamento financeiro ou planejamento futuro
        # (excluir aluno apaga lançamentos em cascata; não permitir para preservar histórico)
        today = timezone.now().date()
        any_financial = FinancialEntry.objects.filter(student=instance).count()
        future_plans = LessonPlan.objects.filter(student=instance, date__gte=today).count()
        if any_financial > 0 or future_plans > 0:
            parts = []
            if any_financial > 0:
                parts.append(f"{any_financial} lançamento(s) financeiro(s) (o histórico seria perdido)")
            if future_plans > 0:
                parts.append(f"{future_plans} planejamento(s) futuro(s)")
            msg = "Não é possível excluir o aluno: " + " e ".join(parts) + ". Mantenha o aluno como Encerrado para preservar o histórico."
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['post'], url_path='generate-monthly-billing')
    def generate_monthly_billing(self, request):
        """
        Gera cobranças do mês para alunos com tipo "Por aula realizada".
        POST /api/students/generate-monthly-billing/
        Body: { "month": "2026-03" } (opcional, default: mês atual)
        """
        if self._is_partner_teacher():
            return Response(
                {'error': 'Professores parceiros não podem gerar cobranças.'},
                status=status.HTTP_403_FORBIDDEN
            )
        month_str = request.data.get('month') or request.query_params.get('month')
        student_id = request.data.get('student_id') or request.query_params.get('student_id')
        if student_id:
            try:
                student_id = int(student_id)
            except (ValueError, TypeError):
                student_id = None
        today = date.today()
        if month_str:
            try:
                year, month = map(int, month_str.split('-'))
            except (ValueError, AttributeError):
                return Response(
                    {'error': 'Mês inválido. Use formato YYYY-MM (ex: 2026-03).'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            year, month = today.year, today.month

        _, last_day = monthrange(year, month)

        students_qs = self.get_queryset().filter(
            billing_type=Student.BILLING_PER_LESSON,
            per_lesson_amount__isnull=False
        ).exclude(per_lesson_amount=0)
        if student_id:
            students_qs = students_qs.filter(id=student_id)
            if not students_qs.exists():
                return Response({
                    'created': [],
                    'skipped': [],
                    'message': 'Aluno não encontrado ou não é do tipo "Por aula realizada" com valor por aula cadastrado.',
                }, status=status.HTTP_200_OK)

        created = []
        updated = []
        skipped = []
        per_lesson_count = students_qs.count()

        for student in students_qs:
            lessons_count = Lesson.objects.filter(
                student=student,
                realized=True,
                date__year=year,
                date__month=month
            ).count()
            if lessons_count == 0:
                skipped.append({'student': student.name, 'reason': 'Nenhuma aula realizada'})
                continue

            due_day = min(student.default_due_day or last_day, last_day)
            due_date = date(year, month, due_day)
            existing_entry = FinancialEntry.objects.filter(
                student=student,
                due_date__year=year,
                due_date__month=month,
                description__startswith='Cobrança por aula realizada'
            ).first()

            if existing_entry:
                # Cobrança já existe: atualizar se houver mais aulas e ainda não pago
                if existing_entry.status in (FinancialEntry.STATUS_PAID, FinancialEntry.STATUS_CANCELLED):
                    skipped.append({'student': student.name, 'reason': 'Cobrança já gerada e paga para este mês'})
                    continue
                # Extrair quantas aulas foram cobradas na descrição: "(3 aulas)"
                match = re.search(r'\((\d+)\s*aulas?\)', existing_entry.description, re.I)
                billed_lessons = int(match.group(1)) if match else 0
                if lessons_count <= billed_lessons:
                    skipped.append({'student': student.name, 'reason': 'Cobrança já gerada para este mês'})
                    continue
                # Atualizar cobrança com novas aulas
                amount = (student.per_lesson_amount or 0) * lessons_count
                if amount <= 0:
                    continue
                new_description = f'Cobrança por aula realizada - {month:02d}/{year} ({lessons_count} aulas)'
                existing_entry.description = new_description
                existing_entry.amount = amount
                existing_entry.save(update_fields=['description', 'amount', 'updated_at'])
                updated.append({
                    'id': existing_entry.id,
                    'student': student.name,
                    'amount': float(amount),
                    'lessons': lessons_count,
                    'previous_lessons': billed_lessons,
                    'due_date': due_date.isoformat(),
                })
                continue

            amount = (student.per_lesson_amount or 0) * lessons_count
            if amount <= 0:
                continue

            description = f'Cobrança por aula realizada - {month:02d}/{year} ({lessons_count} aulas)'
            entry = FinancialEntry.objects.create(
                student=student,
                user=student.user,
                beneficiary_user=student.user,
                description=description,
                amount=amount,
                installments=1,
                current_installment=1,
                issue_date=today,
                due_date=due_date,
                status=FinancialEntry.STATUS_OVERDUE if due_date < today else FinancialEntry.STATUS_PENDING,
                payment_method=student.preferred_payment_method or FinancialEntry.PAYMENT_METHOD_PIX,
            )
            created.append({
                'id': entry.id,
                'student': student.name,
                'amount': float(amount),
                'lessons': lessons_count,
                'due_date': due_date.isoformat(),
            })

        # Mensagem amigável
        if created or updated:
            parts = []
            if created:
                parts.append(f'{len(created)} cobrança(s) gerada(s)')
            if updated:
                parts.append(f'{len(updated)} cobrança(s) atualizada(s) (novas aulas no mês)')
            message = ' e '.join(parts) + ' com sucesso!'
        elif per_lesson_count == 0:
            message = (
                'Nenhum aluno com cobrança por aula realizada. '
                'Cadastre alunos com esse tipo e valor por aula para usar esta função.'
            )
        elif all('já gerada' in s.get('reason', '') for s in skipped):
            message = (
                'Todas as cobranças deste mês já foram geradas para os alunos elegíveis. '
                'Não há nada novo para gerar.'
            )
        elif all(s['reason'] == 'Nenhuma aula realizada' for s in skipped):
            message = (
                'Nenhum aluno teve aulas realizadas este mês. '
                'Marque as aulas como realizadas no calendário e tente novamente.'
            )
        else:
            message = (
                'Nenhuma cobrança gerada. '
                'Os alunos elegíveis já tiveram cobrança gerada ou não tiveram aulas realizadas este mês.'
            )

        return Response({
            'month': f'{year}-{month:02d}',
            'created': created,
            'updated': updated,
            'skipped': skipped,
            'message': message,
        }, status=status.HTTP_200_OK)


class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.select_related("student", "user").all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Admin vê todas as lessons, usuários normais veem apenas as suas
        try:
            is_admin = self.request.user.profile.is_admin
        except UserProfile.DoesNotExist:
            is_admin = False
        
        if not is_admin:
            try:
                user_profile = self.request.user.profile.user_profile
                if user_profile == UserProfile.PROFILE_TEACHER:
                    # Prof. Principal vê todas as aulas dos seus alunos (mantém histórico mesmo após desvincular parceiro)
                    qs = qs.filter(student__user=self.request.user)
                elif user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                    # Parceiro só vê aulas de alunos ATRIBUÍDOS a ele (assigned_teacher)
                    qs = qs.filter(student__user__profile__partner_teachers=self.request.user.profile).filter(student__assigned_teacher=self.request.user)
                else:
                    # Outros usuários veem apenas as suas
                    qs = qs.filter(user=self.request.user)
            except UserProfile.DoesNotExist:
                qs = qs.filter(user=self.request.user)

        # Filtros opcionais via query string:
        # /api/lessons/?date=2026-01-19
        # /api/lessons/?month=2026-01
        # /api/lessons/?start=2026-01-01&end=2026-01-07  (intervalo, ex.: semana)
        # /api/lessons/?student=123  (filtrar por aluno)
        date_str = self.request.query_params.get("date")
        month_str = self.request.query_params.get("month")
        start_str = self.request.query_params.get("start")
        end_str = self.request.query_params.get("end")
        student_param = self.request.query_params.get("student")

        # Filtro por aluno (pode ser combinado com outros filtros)
        if student_param:
            try:
                student_id = int(student_param)
                qs = qs.filter(student_id=student_id)
            except (ValueError, TypeError):
                pass

        if start_str and end_str:
            try:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d").date()
                end_dt = datetime.strptime(end_str, "%Y-%m-%d").date()
                qs = qs.filter(date__gte=start_dt, date__lte=end_dt)
            except ValueError:
                pass
        elif date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                qs = qs.filter(date=date_obj)
            except ValueError:
                pass
        elif month_str:
            try:
                dt = datetime.strptime(month_str, "%Y-%m")
                qs = qs.filter(date__year=dt.year, date__month=dt.month)
            except ValueError:
                pass

        return qs.order_by("date", "time")

    def perform_create(self, serializer):
        # Preenche automaticamente o usuário logado ao criar uma lesson
        serializer.save(user=self.request.user)

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
    queryset = Task.objects.select_related("user").all().order_by("-created_at")
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Admin vê todas as tasks, usuários normais veem apenas as suas
        try:
            is_admin = self.request.user.profile.is_admin
        except UserProfile.DoesNotExist:
            is_admin = False
        
        if not is_admin:
            try:
                user_profile = self.request.user.profile.user_profile
                if user_profile == UserProfile.PROFILE_TEACHER:
                    # Prof. Principal vê suas tasks + tasks dos parceiros vinculados
                    partner_ids = list(self.request.user.profile.partner_teachers.values_list('user_id', flat=True))
                    partner_ids.append(self.request.user.id)
                    qs = qs.filter(user_id__in=partner_ids)
                else:
                    # Outros usuários veem apenas as suas
                    qs = qs.filter(user=self.request.user)
            except UserProfile.DoesNotExist:
                qs = qs.filter(user=self.request.user)
        
        return qs

    def perform_create(self, serializer):
        # Preenche automaticamente o usuário logado ao criar uma task
        serializer.save(user=self.request.user)

from django.views.generic import TemplateView


def _user_is_in_trial(user):
    """True se o usuário está no trial gratuito (7 dias sem cartão)."""
    try:
        profile = user.profile
        trial_ends = getattr(profile, 'trial_ends_at', None)
        return bool(trial_ends and timezone.now() < trial_ends)
    except Exception:
        return False


def _user_has_active_subscription(user):
    """
    Retorna True se o usuário pode acessar o sistema sem bloqueio por assinatura.
    - Django staff/superuser: sempre permite
    - is_admin ou subscription_exempt no perfil: sempre permite
    - Trial gratuito: trial_ends_at no futuro (7 dias sem cartão)
    - Prof. parceiro: permite apenas se o dono da conta tiver assinatura ativa
    - Demais: exige assinatura ativa
    """
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return True
    try:
        profile = user.profile
        if profile.is_admin or getattr(profile, 'subscription_exempt', False):
            return True
        # Trial gratuito (7 dias sem cartão): acesso enquanto trial_ends_at > agora
        trial_ends = getattr(profile, 'trial_ends_at', None)
        if trial_ends and timezone.now() < trial_ends:
            return True
        if profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
            owner = UserProfile.objects.filter(partner_teachers=profile).select_related('user').first()
            if owner:
                try:
                    return owner.user.subscription.is_active
                except Subscription.DoesNotExist:
                    return False
            return False
        return user.subscription.is_active
    except (Subscription.DoesNotExist, UserProfile.DoesNotExist):
        return False


class AlunosView(TemplateView):
    """View para renderizar a página de alunos"""
    template_name = "alunos_new.html"
    
    def dispatch(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        if not request.user.is_authenticated:
            return redirect('/login/')
        if not _user_has_active_subscription(request.user):
            return redirect('planos')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            profile = self.request.user.profile
            context['user_is_admin'] = profile.is_admin
            context['is_partner_teacher'] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
            if profile.user_profile == UserProfile.PROFILE_TEACHER:
                partners = list(profile.partner_teachers.select_related('user').all())
                context['assignable_teachers'] = [
                    {'id': self.request.user.id, 'name': self.request.user.get_full_name() or self.request.user.username}
                ] + [{'id': p.user.id, 'name': p.user.get_full_name() or p.user.username} for p in partners]
            else:
                context['assignable_teachers'] = []
        except UserProfile.DoesNotExist:
            context['user_is_admin'] = False
            context['is_partner_teacher'] = False
            context['assignable_teachers'] = []
        return context


class AlunoDetalheView(TemplateView):
    """Página de detalhe de um aluno (ficha completa). Acesso: /alunos/<student_id>/"""
    template_name = "aluno_detalhe.html"

    def dispatch(self, request, *args, **kwargs):
        from django.http import Http404
        if not request.user.is_authenticated:
            return redirect('/login/')
        if not _user_has_active_subscription(request.user):
            return redirect('planos')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset_students(self):
        """Mesmo critério do StudentViewSet: dono vê os seus; parceiro vê os atribuídos a ele; admin vê todos."""
        qs = Student.objects.select_related("user", "assigned_teacher").all()
        try:
            is_admin = self.request.user.profile.is_admin
            user_profile = self.request.user.profile.user_profile
        except UserProfile.DoesNotExist:
            is_admin = False
            user_profile = None
        if is_admin:
            return qs
        if user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
            qs = qs.filter(user__profile__partner_teachers=self.request.user.profile).filter(assigned_teacher=self.request.user)
        else:
            qs = qs.filter(user=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student_id = kwargs.get('student_id')
        qs = self.get_queryset_students()
        student = get_object_or_404(qs, id=student_id)
        context['student'] = student
        try:
            context['is_partner_teacher'] = self.request.user.profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
        except UserProfile.DoesNotExist:
            context['is_partner_teacher'] = False

        # --- Parte 1: Aulas (Lesson) ---
        today = timezone.now().date()
        lessons_qs = student.lessons.all()
        context['next_lesson'] = (
            lessons_qs.filter(realized=False)
            .exclude(status='canceled')
            .filter(date__gte=today)
            .order_by('date', 'time')
            .first()
        )
        context['last_lessons'] = lessons_qs.order_by('-date', '-time')[:5]
        context['lessons_realized_count'] = lessons_qs.filter(realized=True).count()
        context['lessons_total'] = student.lessons_total or 0

        # Calendário: mês atual com dias de aula realizada vs agendada
        start_month = today.replace(day=1)
        _, last_day = monthrange(today.year, today.month)
        end_month = today.replace(day=last_day)
        lessons_in_month = lessons_qs.filter(date__gte=start_month, date__lte=end_month)
        cal_done = [l.date.day for l in lessons_in_month if l.realized]
        cal_upcoming = [
            l.date.day for l in lessons_in_month
            if not l.realized and l.status != 'canceled'
        ]
        cal_key = f"{today.year}-{today.month - 1}"  # JS month 0-indexed
        context['cal_class_data'] = json.dumps({
            cal_key: {"done": cal_done, "upcoming": cal_upcoming}
        })
        context['current_cal_year'] = today.year
        context['current_cal_month'] = today.month - 1

        # --- Parte 2: Financeiro (FinancialEntry = lançamentos a receber) ---
        entries_pending = student.financial_entries.exclude(
            status__in=[FinancialEntry.STATUS_PAID, FinancialEntry.STATUS_CANCELLED]
        )
        has_overdue = entries_pending.filter(
            Q(status=FinancialEntry.STATUS_OVERDUE) |
            Q(status=FinancialEntry.STATUS_PENDING, due_date__lt=today)
        ).exists()
        next_entry = (
            entries_pending
            .order_by('due_date')
            .first()
        )
        if has_overdue:
            context['finance_status'] = 'overdue'
        elif next_entry:
            context['finance_status'] = 'pending'
        else:
            context['finance_status'] = 'ok'
        context['next_invoice'] = next_entry  # FinancialEntry; template usa .due_date igual

        # --- Parte 4: Materiais do aluno (separados de Planejamento) ---
        materiais_list = []
        materials_qs = StudentMaterial.objects.filter(student=student).order_by("-material_date", "-created_at")
        AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".aac"}
        VIDEO_EXT = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
        for mat in materials_qs:
            if mat.material_type == StudentMaterial.TYPE_LINK:
                file_type = "link"
                url = mat.external_url
            else:
                ext = os.path.splitext((mat.file.name if mat.file else "") or "")[1].lower()
                if ext == ".pdf":
                    file_type = "pdf"
                elif ext in AUDIO_EXT:
                    file_type = "audio"
                elif ext in VIDEO_EXT:
                    file_type = "video"
                else:
                    file_type = "other"
                url = mat.file.url if mat.file else ""
                if self.request and url:
                    url = self.request.build_absolute_uri(url)
            materiais_list.append({
                "material_id": mat.id,
                "url": url,
                "original_filename": mat.title or "Material",
                "file_type": file_type,
                "plan_date": mat.material_date,
                "uploaded_at": mat.created_at,
                "external_url": mat.external_url or "",
            })
        context["materiais"] = materiais_list
        from django.db.models import Sum
        total_bytes = materials_qs.aggregate(total=Sum("file_size")).get("total") or 0
        context["materiais_total_bytes"] = total_bytes
        context["materiais_count"] = materials_qs.count()

        # Homework (KPI + resumo)
        from django.db.models import Count, Q as Qm
        hw_agg = StudentHomework.objects.filter(student=student).aggregate(
            hw_total=Count("id"),
            hw_done=Count("id", filter=Qm(status=StudentHomework.STATUS_DONE)),
        )
        hw_total = hw_agg["hw_total"] or 0
        hw_done = hw_agg["hw_done"] or 0
        context["hw_total"] = hw_total
        context["hw_done"] = hw_done
        context["hw_pct"] = int(round(100 * hw_done / hw_total)) if hw_total else 0

        try:
            profile = self.request.user.profile
            if profile.user_profile == UserProfile.PROFILE_TEACHER:
                partners = list(profile.partner_teachers.select_related("user").all())
                context["assignable_teachers"] = [
                    {"id": self.request.user.id, "name": self.request.user.get_full_name() or self.request.user.username}
                ] + [{"id": p.user.id, "name": p.user.get_full_name() or p.user.username} for p in partners]
            else:
                context["assignable_teachers"] = []
        except UserProfile.DoesNotExist:
            context["assignable_teachers"] = []

        return context


class StudentAreaView(TemplateView):
    """
    Área do Aluno pública (sem login), acessada via token:
    /aluno/<token>/
    """

    template_name = "area_aluno.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token_val = kwargs.get("token") or ""
        token_obj = get_object_or_404(StudentShareToken, token=token_val, revoked_at__isnull=True)
        student = token_obj.student
        teacher_name = student.user.get_full_name() or student.user.username
        context["student"] = student
        context["teacher_name"] = teacher_name
        context["share_token"] = token_obj.token

        today = timezone.now().date()
        months_pt = [
            "janeiro",
            "fevereiro",
            "março",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        ]
        months_pt_short = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
        weekdays_pt = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

        # --- Next lesson highlight (current & upcoming) ---
        next_lesson = (
            student.lessons.all()
            .filter(realized=False)
            .exclude(status="canceled")
            .filter(date__gte=today)
            .order_by("date", "time")
            .first()
        )
        if next_lesson:
            context["next_lesson"] = {
                "title": next_lesson.title,
                "info": next_lesson.info or "",
                "date_day": next_lesson.date.day,
                "date_month": months_pt[next_lesson.date.month - 1],
                "date_weekday": weekdays_pt[next_lesson.date.weekday()],
                "date_display": next_lesson.date.strftime("%d/%m"),
                "time_str": next_lesson.time.strftime("%H:%M") if next_lesson.time else "",
            }
        else:
            context["next_lesson"] = None

        # --- Last realized lesson (for stats) ---
        realized_lessons_qs = student.lessons.all().filter(
            Q(realized=True) | Q(status__in=["done", "realized", "realizada"])
        )
        last_realized = realized_lessons_qs.order_by("-date", "-time").first()
        if last_realized:
            context["last_realized"] = {
                "date_display": last_realized.date.strftime("%d/%m"),
                "title": last_realized.title,
            }
        else:
            context["last_realized"] = None

        # --- KPIs ---
        # Usa contagem real de aulas realizadas para evitar KPI desatualizado.
        lessons_realized_count = realized_lessons_qs.count()
        lessons_total_count = int(getattr(student, "lessons_total", 0) or 0)
        context["lessons_realized_count"] = lessons_realized_count
        context["lessons_total_count"] = lessons_total_count

        # "Desde ..." for display
        first_realized = realized_lessons_qs.order_by("date", "time").first()
        if first_realized:
            context["lessons_realized_since"] = first_realized.date.strftime("%b/%Y").replace("Jan", "jan").replace("Feb", "fev").replace("Mar", "mar").replace("Apr", "abr").replace("May", "mai").replace("Jun", "jun").replace("Jul", "jul").replace("Aug", "ago").replace("Sep", "set").replace("Oct", "out").replace("Nov", "nov").replace("Dec", "dez")
        else:
            context["lessons_realized_since"] = "—"

        # --- Homework KPIs + cards data ---
        homeworks_qs = student.homeworks.prefetch_related("messages").all().order_by("-updated_at", "-created_at")
        hw_total = homeworks_qs.count()
        hw_done = homeworks_qs.filter(status=StudentHomework.STATUS_DONE).count()
        context["hw_total"] = hw_total
        context["hw_done"] = hw_done
        context["hw_pct"] = int(round(100 * hw_done / hw_total)) if hw_total else 0

        hw_pending = homeworks_qs.filter(status=StudentHomework.STATUS_PENDING)
        hw_in_progress_count = hw_pending.filter(student_response__isnull=False).exclude(student_response__exact="").count()
        hw_not_started_count = hw_pending.count() - hw_in_progress_count
        context["hw_in_progress_count"] = hw_in_progress_count
        context["hw_not_started_count"] = hw_not_started_count

        # Cards (public read-only)
        pending_cards = []
        for hw in hw_pending:
            due_label = hw.due_date.strftime("%d/%m") if hw.due_date else "—"
            messages = list(hw.messages.all().order_by("created_at", "id"))
            msg_payload = [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "sender_label": "Aluno" if m.sender == StudentHomeworkMessage.SENDER_STUDENT else "Professor",
                    "message": m.message,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ]
            # Sem mock: tarefa pendente começa em 0% e só vai a 100% quando concluída.
            progress_percent = 0
            pending_cards.append(
                {
                    "id": hw.id,
                    "title": hw.title,
                    "description": hw.description or "",
                    "due_label": due_label,
                    "progress_percent": progress_percent,
                    "progress_width": f"{progress_percent}%",
                    "teacher_feedback": hw.teacher_feedback or "",
                    "student_response": hw.student_response or "",
                    "messages": msg_payload,
                }
            )

        done_cards = []
        for hw in homeworks_qs.filter(status=StudentHomework.STATUS_DONE):
            submitted_label = hw.updated_at.date().strftime("%d/%m") if hw.updated_at else "—"
            messages = list(hw.messages.all().order_by("created_at", "id"))
            msg_payload = [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "sender_label": "Aluno" if m.sender == StudentHomeworkMessage.SENDER_STUDENT else "Professor",
                    "message": m.message,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ]
            done_cards.append(
                {
                    "id": hw.id,
                    "title": hw.title,
                    "description": hw.description or "",
                    "submitted_label": submitted_label,
                    "progress_percent": 100,
                    "progress_width": "100%",
                    "teacher_feedback": hw.teacher_feedback or "",
                    "student_response": hw.student_response or "",
                    "messages": msg_payload,
                }
            )

        context["hw_pending_cards"] = pending_cards
        context["hw_done_cards"] = done_cards

        # --- Dedication breakdown (simple, based on pending due + comments + lessons) ---
        hw_no_prazo = hw_pending.filter(due_date__gte=today).count() if hw_pending.exists() else 0
        hw_comment_count = homeworks_qs.exclude(student_response__exact="").exclude(student_response__isnull=True).count()
        context["ded_hw_no_prazo"] = hw_no_prazo
        context["ded_hw_comments"] = hw_comment_count
        context["ded_lessons"] = lessons_total_count
        # dedication dots: 0..5
        # Normalize comments vs total homework to decide how many dots fill.
        if hw_total:
            dot_fill = int(round(4 * (hw_comment_count / hw_total)))
        else:
            dot_fill = 0
        context["ded_dot_fill"] = min(5, max(0, dot_fill))
        if context["ded_dot_fill"] >= 4:
            context["dedication_label"] = "Alta dedicação"
        elif context["ded_dot_fill"] >= 2:
            context["dedication_label"] = "Boa consistência"
        else:
            context["dedication_label"] = "Começando agora"

        # --- Materials grouped by month/date (somente StudentMaterial) ---
        materials_qs = StudentMaterial.objects.filter(student=student).order_by("-material_date", "-created_at")
        AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".aac"}
        VIDEO_EXT = {".mp4", ".webm", ".mov", ".avi", ".mkv"}

        def _file_type(mat):
            if mat.material_type == StudentMaterial.TYPE_LINK:
                return "link"
            ext = os.path.splitext((mat.file.name if mat.file else "") or "")[1].lower()
            if ext == ".pdf":
                return "pdf"
            if ext in AUDIO_EXT:
                return "audio"
            if ext in VIDEO_EXT:
                return "video"
            return "file"

        materials_map = {}  # month_label -> date_label -> [items]
        for mat in materials_qs:
            plan_date = mat.material_date
            month_label = f"{months_pt[plan_date.month - 1].capitalize()} {plan_date.year}"
            date_label = f"{plan_date.day:02d} de {months_pt[plan_date.month - 1]}"
            ftype = _file_type(mat)
            if ftype == "pdf":
                type_tag = "PDF"
            elif ftype == "audio":
                type_tag = "Áudio"
            elif ftype == "video":
                type_tag = "Vídeo"
            elif ftype == "link":
                type_tag = "Link"
            else:
                type_tag = "Arquivo"
            obs = ""
            url = mat.external_url if mat.material_type == StudentMaterial.TYPE_LINK else (self.request.build_absolute_uri(mat.file.url) if mat.file else "")
            materials_map.setdefault(month_label, {}).setdefault(date_label, []).append(
                {
                    "url": url,
                    "original_filename": mat.title or "Material",
                    "file_type": ftype,
                    "type_tag": type_tag,
                    "plan_date": plan_date.isoformat() if plan_date else None,
                    "obs": obs,
                }
            )

        materials_months = []
        for month_label, date_groups in materials_map.items():
            # date_groups is an ordered dict by insertion (we already ordered by date desc)
            date_items = []
            for date_label, items in date_groups.items():
                date_items.append({"date_label": date_label, "items": items})
            materials_months.append({"month_label": month_label, "date_groups": date_items})
        # Keep newest month first
        materials_months.sort(key=lambda mg: mg["month_label"], reverse=True)
        context["materials_months"] = materials_months

        # --- Calendar: this month ---
        cal_year = today.year
        cal_month0 = today.month - 1  # JS uses 0-indexed
        cal_month_label = f"{months_pt[cal_month0].capitalize()} {cal_year}"
        context["cal_year"] = cal_year
        context["cal_month0"] = cal_month0
        context["cal_month_label"] = cal_month_label

        lessons_in_month = (
            student.lessons.all()
            .filter(date__year=cal_year, date__month=cal_month0 + 1)
            .order_by("date", "time")
        )

        done_days = sorted({l.date.day for l in lessons_in_month if l.realized})
        upcoming_days = sorted({l.date.day for l in lessons_in_month if (not l.realized and l.status != "canceled")})
        context["cal_class_done_days"] = done_days
        context["cal_class_upcoming_days"] = upcoming_days

        lessons_in_month_list = []
        for l in lessons_in_month:
            badge_class = "realizada" if l.realized else ("cancelada" if l.status == "canceled" else "agendada")
            badge_label = "Realizada" if l.realized else ("Cancelada" if l.status == "canceled" else "Agendada")
            lessons_in_month_list.append(
                {
                    "date_day": l.date.day,
                    "date_month_short": months_pt_short[l.date.month - 1],
                    "time_str": l.time.strftime("%H:%M") if l.time else "",
                    "topic": l.title,
                    "obs": l.info or "",
                    "badge_class": badge_class,
                    "badge_label": badge_label,
                }
            )
        context["lessons_in_month_list"] = lessons_in_month_list

        # --- JS-friendly JSON blobs (for rendering public mock -> real data) ---
        context["materials_months_json"] = json.dumps(materials_months, ensure_ascii=False)
        context["hw_pending_cards_json"] = json.dumps(pending_cards, ensure_ascii=False)
        context["hw_done_cards_json"] = json.dumps(done_cards, ensure_ascii=False)
        context["lessons_in_month_list_json"] = json.dumps(lessons_in_month_list, ensure_ascii=False)
        context["cal_class_done_days_json"] = json.dumps(done_days, ensure_ascii=False)
        context["cal_class_upcoming_days_json"] = json.dumps(upcoming_days, ensure_ascii=False)

        return context


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def student_share_link(request, student_id):
    """
    Retorna URL do link de acesso público da Área do Aluno.
    Gera token se não existir.
    """
    view = AlunoDetalheView()
    view.request = request
    try:
        qs = view.get_queryset_students()
        student = qs.get(id=student_id)
    except Student.DoesNotExist:
        return Response({"detail": "Aluno não encontrado ou sem permissão."}, status=status.HTTP_404_NOT_FOUND)

    token_obj = StudentShareToken.get_active_token(student)
    if not token_obj:
        token_obj = StudentShareToken.create_new_active_token(student)

    url = request.build_absolute_uri(reverse("aluno-area-token", kwargs={"token": token_obj.token}))
    return Response({"url": url})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def student_share_link_regenerate(request, student_id):
    """
    Revoga o token ativo e gera um novo.
    """
    view = AlunoDetalheView()
    view.request = request
    try:
        qs = view.get_queryset_students()
        student = qs.get(id=student_id)
    except Student.DoesNotExist:
        return Response({"detail": "Aluno não encontrado ou sem permissão."}, status=status.HTTP_404_NOT_FOUND)

    token_obj = StudentShareToken.create_new_active_token(student)
    url = request.build_absolute_uri(reverse("aluno-area-token", kwargs={"token": token_obj.token}))
    return Response({"url": url})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def public_area_aluno_homework_comment(request, token, homework_id):
    """
    Permite que o aluno (via token público) envie/atualize student_response do homework.
    Endpoint para uso na Área do Aluno (pública, sem login).
    """
    try:
        token_obj = StudentShareToken.objects.select_related("student").get(
            token=token, revoked_at__isnull=True
        )
    except StudentShareToken.DoesNotExist:
        return Response({"detail": "Token inválido ou revogado."}, status=status.HTTP_404_NOT_FOUND)

    try:
        hw = StudentHomework.objects.get(id=homework_id, student=token_obj.student)
    except StudentHomework.DoesNotExist:
        return Response({"detail": "Homework não encontrado."}, status=status.HTTP_404_NOT_FOUND)

    # DRF parseia JSON automaticamente quando Content-Type = application/json
    payload = request.data if hasattr(request, "data") else {}
    student_response = (payload.get("student_response") or "").strip()

    if not student_response:
        return Response({"detail": "Mensagem vazia."}, status=status.HTTP_400_BAD_REQUEST)

    StudentHomeworkMessage.objects.create(
        homework=hw,
        sender=StudentHomeworkMessage.SENDER_STUDENT,
        message=student_response,
        created_by=None,
    )
    # Mantém compatibilidade com campos legados.
    hw.student_response = student_response
    hw.save(update_fields=["student_response", "updated_at"])

    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_student_material(request, student_id):
    """
    Upload rápido de material na ficha do aluno.
    Cria (ou reutiliza) um LessonPlan para o aluno e delega a lógica de anexo
    para LessonPlanAttachment / LessonPlanAttachmentSerializer.
    """
    # Reutiliza a mesma validação de permissão da tela de detalhe
    # (dono da conta, parceiro atribuído ou admin).
    view = AlunoDetalheView()
    view.request = request
    try:
        qs = view.get_queryset_students()
        student = qs.get(id=student_id)
    except Student.DoesNotExist:
        return Response({"error": "Aluno não encontrado ou sem permissão."}, status=status.HTTP_404_NOT_FOUND)

    django_request = getattr(request, "_request", None)
    external_url = ""
    if django_request:
        external_url = (django_request.POST.get("external_url") or "").strip()
    has_file = "file" in request.FILES
    if (not has_file) and (not external_url):
        return Response({"error": "Envie um arquivo ou informe um link externo."}, status=status.HTTP_400_BAD_REQUEST)

    today = timezone.now().date()
    plan_date = today
    if django_request:
        raw = (django_request.POST.get("plan_date") or "").strip()
        if raw:
            try:
                plan_date = datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                plan_date = today

    # Caso de material por link (sem upload de arquivo)
    if external_url and not has_file:
        if not (external_url.startswith("http://") or external_url.startswith("https://")):
            return Response({"error": "Informe um link válido iniciando com http:// ou https://"}, status=status.HTTP_400_BAD_REQUEST)
        material = StudentMaterial.objects.create(
            student=student,
            user=request.user,
            title=(django_request.POST.get("display_title") or "").strip()[:200] or external_url,
            material_type=StudentMaterial.TYPE_LINK,
            external_url=external_url,
            file_size=0,
            material_date=plan_date,
        )
        return Response({"ok": True, "material_id": material.id, "type": "link", "url": external_url}, status=status.HTTP_201_CREATED)

    file = request.FILES.get("file")
    if not file:
        return Response({"error": "Arquivo inválido."}, status=status.HTTP_400_BAD_REQUEST)
    MAX_FILE_SIZE = getattr(settings, "PLANNING_ATTACHMENT_MAX_FILE_SIZE", 10 * 1024 * 1024)
    if file.size > MAX_FILE_SIZE:
        return Response({"error": f"Arquivo muito grande. Tamanho máximo: {int(MAX_FILE_SIZE / (1024*1024))}MB"}, status=status.HTTP_400_BAD_REQUEST)
    title = (django_request.POST.get("display_title") or "").strip()[:200] or file.name
    material = StudentMaterial.objects.create(
        student=student,
        user=request.user,
        title=title,
        material_type=StudentMaterial.TYPE_FILE,
        file=file,
        file_size=file.size,
        material_date=plan_date,
    )
    return Response({"ok": True, "material_id": material.id, "type": "file"}, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_student_material(request, student_id, material_id):
    view = AlunoDetalheView()
    view.request = request
    try:
        qs = view.get_queryset_students()
        _student = qs.get(id=student_id)
    except Student.DoesNotExist:
        return Response({"error": "Aluno não encontrado ou sem permissão."}, status=status.HTTP_404_NOT_FOUND)
    try:
        material = StudentMaterial.objects.get(id=material_id, student_id=student_id)
    except StudentMaterial.DoesNotExist:
        return Response({"error": "Material não encontrado."}, status=status.HTTP_404_NOT_FOUND)
    if material.file:
        material.file.delete()
    material.delete()
    return Response({"ok": True}, status=status.HTTP_200_OK)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_student_material(request, student_id, material_id):
    view = AlunoDetalheView()
    view.request = request
    try:
        qs = view.get_queryset_students()
        _student = qs.get(id=student_id)
    except Student.DoesNotExist:
        return Response({"error": "Aluno não encontrado ou sem permissão."}, status=status.HTTP_404_NOT_FOUND)
    try:
        material = StudentMaterial.objects.get(id=material_id, student_id=student_id)
    except StudentMaterial.DoesNotExist:
        return Response({"error": "Material não encontrado."}, status=status.HTTP_404_NOT_FOUND)

    payload = request.data if hasattr(request, "data") else {}
    title = (payload.get("title") or "").strip()
    raw_date = (payload.get("material_date") or "").strip()
    external_url = (payload.get("external_url") or "").strip()

    if title:
        material.title = title[:200]
    if raw_date:
        try:
            material.material_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Data inválida."}, status=status.HTTP_400_BAD_REQUEST)
    if material.material_type == StudentMaterial.TYPE_LINK and external_url:
        if not (external_url.startswith("http://") or external_url.startswith("https://")):
            return Response({"error": "Informe um link válido iniciando com http:// ou https://"}, status=status.HTTP_400_BAD_REQUEST)
        material.external_url = external_url

    material.save(update_fields=["title", "material_date", "external_url", "updated_at"])
    return Response({"ok": True}, status=status.HTTP_200_OK)


class FinanceView(TemplateView):
    """View para renderizar a página financeira (lançamentos a receber)"""
    template_name = "finance_refatorado.html"

    def dispatch(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        if not request.user.is_authenticated:
            return redirect('/login/')
        if not _user_has_active_subscription(request.user):
            return redirect('planos')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            profile = self.request.user.profile
            context['user_is_admin'] = profile.is_admin
            context['is_partner_teacher'] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
            if profile.user_profile == UserProfile.PROFILE_TEACHER:
                partners = list(profile.partner_teachers.select_related('user').all())
                context['assignable_teachers'] = [
                    {'id': self.request.user.id, 'name': self.request.user.get_full_name() or self.request.user.username}
                ] + [{'id': p.user.id, 'name': p.user.get_full_name() or p.user.username} for p in partners]
            else:
                context['assignable_teachers'] = []
        except UserProfile.DoesNotExist:
            context['user_is_admin'] = False
            context['is_partner_teacher'] = False
            context['assignable_teachers'] = []
        return context


class ReciboView(TemplateView):
    """View para renderizar o recibo de um lançamento financeiro"""
    template_name = "recibo.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entry_id = self.kwargs.get('entry_id')
        qs = get_financial_entries_queryset_for_user(self.request)
        try:
            entry = qs.get(pk=entry_id)
        except FinancialEntry.DoesNotExist:
            context['receipt_data'] = None
            context['entry_not_found'] = True
            return context

        student = entry.student
        beneficiary = entry.beneficiary_user or entry.user
        teacher_name = beneficiary.get_full_name() or beneficiary.username

        payment_method_labels = {
            'pix': 'PIX',
            'cash': 'Dinheiro',
            'card': 'Cartão',
            'transfer': 'Transferência',
            'other': 'Outro',
        }
        method_label = payment_method_labels.get(entry.payment_method or 'pix', 'PIX')

        def fmt_date(d):
            return d.strftime('%d/%m/%Y') if d else '-'

        def fmt_datetime(dt):
            return dt.strftime('%d/%m/%Y %H:%M') if dt else '-'

        # Usar horário de Brasília no recibo
        try:
            from zoneinfo import ZoneInfo
            now_brazil = timezone.now().astimezone(ZoneInfo('America/Sao_Paulo'))
        except ImportError:
            import pytz
            now_brazil = timezone.now().astimezone(pytz.timezone('America/Sao_Paulo'))

        paid_at_str = 'Pago em ' + fmt_date(entry.payment_date) if entry.status == FinancialEntry.STATUS_PAID and entry.payment_date else '-'
        installment_str = f"{entry.current_installment} / {entry.installments}" if entry.installments > 1 else "1 / 1"

        contact_parts = []
        if student.phone:
            contact_parts.append(str(student.phone))
        if student.email:
            contact_parts.append(str(student.email))
        student_contact = ' • '.join(contact_parts) if contact_parts else '-'

        import random
        import string
        hash_chars = string.ascii_uppercase + string.digits
        hash_val = '-'.join([''.join(random.choices(hash_chars, k=4)) for _ in range(3)])

        receipt_id = f"REC-{entry.due_date.year}-{str(entry.id).zfill(6)}" if entry.due_date else f"REC-{entry.id}"

        context['receipt_data'] = {
            'receipt_id': receipt_id,
            'issued_at': fmt_datetime(now_brazil),
            'status': 'PAGO' if entry.status == FinancialEntry.STATUS_PAID else entry.status.upper(),
            'student_name': student.name,
            'student_contact': student_contact,
            'teacher_name': f"{teacher_name} (Conta Principal)" if beneficiary == self.request.user else teacher_name,
            'system_name': 'EDUCAflowOne • educaflowone.com.br',
            'amount': float(entry.amount),
            'paid_at': paid_at_str,
            'method': method_label,
            'installment': installment_str,
            'due_date': fmt_date(entry.due_date),
            'description': entry.description,
            'reference': f"FIN-ENTRY-{entry.id}",
            'notes': entry.notes or 'Pagamento confirmado. Caso necessário, apresente este recibo para conferência.',
            'hash': hash_val,
            'issued_by': self.request.user.get_full_name() or self.request.user.username,
        }
        context['entry_not_found'] = False
        return context


class HomeView(View):
    """
    Rota principal (/): usuário não logado → landing page; logado → dashboard/planos/calendar.
    Permite usar educaflow.com.br no Instagram levando direto à landing (trilha de venda).
    """
    def get(self, request):
        if not request.user.is_authenticated:
            return render(request, "test_landing_v5.html")
        # Sincronizar assinatura com Stripe antes de checar (corrige trial/pendente)
        try:
            sub = request.user.subscription
            _sync_subscription_from_stripe(sub)
            sub.refresh_from_db()
        except (Subscription.DoesNotExist, Exception):
            pass
        if not _user_has_active_subscription(request.user):
            return redirect('planos')
        view_param = request.GET.get('view')
        if view_param:
            if view_param == 'view-tasks':
                return redirect('tasks-v2')
            context = self._get_index_context(request)
            return render(request, "index.html", context)
        try:
            if request.user.profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                return redirect('calendar-new')
        except UserProfile.DoesNotExist:
            pass
        return redirect('dashboard-home')

    def _get_index_context(self, request):
        try:
            profile = request.user.profile
            user_is_admin = profile.is_admin
            is_partner_teacher = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
            if profile.user_profile == UserProfile.PROFILE_TEACHER:
                partners = list(profile.partner_teachers.select_related('user').all())
                assignable_teachers = [
                    {'id': request.user.id, 'name': request.user.get_full_name() or request.user.username}
                ] + [{'id': p.user.id, 'name': p.user.get_full_name() or p.user.username} for p in partners]
            else:
                assignable_teachers = []
        except UserProfile.DoesNotExist:
            user_is_admin = False
            is_partner_teacher = False
            assignable_teachers = []
        return {
            'user_is_admin': user_is_admin,
            'is_partner_teacher': is_partner_teacher,
            'assignable_teachers': assignable_teachers,
        }


class DashboardView(TemplateView):
    """View para rota raiz (quando acessada com ?view=...) - renderiza index.html. Raiz sem view usa HomeView."""
    template_name = "index.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            profile = self.request.user.profile
            context['user_is_admin'] = profile.is_admin
            context['is_partner_teacher'] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
            if profile.user_profile == UserProfile.PROFILE_TEACHER:
                partners = list(profile.partner_teachers.select_related('user').all())
                context['assignable_teachers'] = [
                    {'id': self.request.user.id, 'name': self.request.user.get_full_name() or self.request.user.username}
                ] + [{'id': p.user.id, 'name': p.user.get_full_name() or p.user.username} for p in partners]
            else:
                context['assignable_teachers'] = []
        except UserProfile.DoesNotExist:
            context['user_is_admin'] = False
            context['is_partner_teacher'] = False
            context['assignable_teachers'] = []
        return context
    
    def dispatch(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        if not request.user.is_authenticated:
            return redirect('login')
        if not _user_has_active_subscription(request.user):
            return redirect('planos')
        
        # Se houver parâmetro view na URL, renderizar index.html (para view-tasks, view-billing, etc)
        view_param = request.GET.get('view')
        if view_param:
            if view_param == 'view-tasks':
                return redirect('tasks-v2')
            return super().dispatch(request, *args, **kwargs)
        
        # Caso contrário: Prof. Parceiro vai para calendário; demais para dashboard
        try:
            if request.user.profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                return redirect('calendar-new')
        except UserProfile.DoesNotExist:
            pass
        return redirect('dashboard-home')

class DashboardHomeView(TemplateView):
    template_name = "dashboard_home.html"
    login_required = True
    
    def dispatch(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        if not request.user.is_authenticated:
            return redirect('login')
        if not _user_has_active_subscription(request.user):
            return redirect('planos')
        return super().dispatch(request, *args, **kwargs)


class TasksV2View(TemplateView):
    """
    Página standalone para testar o novo layout de Tarefas (tasks_v2.html).
    Não integra ainda no menu sidebar / index.
    """
    template_name = "tasks_v2.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            profile = self.request.user.profile
            ctx["user_is_admin"] = profile.is_admin
            ctx["is_partner_teacher"] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
        except Exception:
            ctx["user_is_admin"] = False
            ctx["is_partner_teacher"] = False
        return ctx

    def dispatch(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        if not request.user.is_authenticated:
            return redirect('login')
        if not _user_has_active_subscription(request.user):
            return redirect('planos')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            profile = self.request.user.profile
            context['user_is_admin'] = profile.is_admin
            context['is_partner_teacher'] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
        except UserProfile.DoesNotExist:
            context['user_is_admin'] = False
            context['is_partner_teacher'] = False
        return context

class PerfilView(TemplateView):
    template_name = "perfil_user.html"
    login_required = True
    
    def dispatch(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        if not request.user.is_authenticated:
            return redirect('login')
        if not _user_has_active_subscription(request.user):
            return redirect('planos')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['user_is_admin'] = self.request.user.profile.is_admin
            context['is_partner_teacher'] = self.request.user.profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
        except UserProfile.DoesNotExist:
            context['user_is_admin'] = False
            context['is_partner_teacher'] = False
        return context


class TutorialView(TemplateView):
    template_name = "tutorial.html"
    login_required = True

    def dispatch(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        if not request.user.is_authenticated:
            return redirect("login")
        if not _user_has_active_subscription(request.user):
            return redirect("planos")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            profile = self.request.user.profile
            context['user_is_admin'] = profile.is_admin
            context['is_partner_teacher'] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
        except UserProfile.DoesNotExist:
            context['user_is_admin'] = False
            context['is_partner_teacher'] = False
        return context


class PlanningListView(TemplateView):
    template_name = "planning_list.html"
    login_required = True

    def dispatch(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        if not request.user.is_authenticated:
            return redirect("login")
        if not _user_has_active_subscription(request.user):
            return redirect("planos")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            profile = self.request.user.profile
            context['user_is_admin'] = profile.is_admin
            context['is_partner_teacher'] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
            if profile.user_profile == UserProfile.PROFILE_TEACHER:
                partners = list(profile.partner_teachers.select_related('user').all())
                context['assignable_teachers'] = [
                    {'id': self.request.user.id, 'name': self.request.user.get_full_name() or self.request.user.username}
                ] + [{'id': p.user.id, 'name': p.user.get_full_name() or p.user.username} for p in partners]
            else:
                context['assignable_teachers'] = []
        except UserProfile.DoesNotExist:
            context['user_is_admin'] = False
            context['is_partner_teacher'] = False
            context['assignable_teachers'] = []
        return context


def planning_edit_redirect(request):
    from django.shortcuts import redirect
    from urllib.parse import urlencode
    if not request.user.is_authenticated:
        return redirect("login")
    plan_id = request.GET.get("id", "").strip()
    qs = urlencode({"view": "view-planning", "id": plan_id} if plan_id else {"view": "view-planning"})
    return redirect("/?" + qs)


def planning_new_redirect(request):
    from django.shortcuts import redirect
    if not request.user.is_authenticated:
        return redirect("login")
    return redirect("/?view=view-planning")


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_planning_attachment(request, plan_id):
    """
    Upload de anexo para um planejamento.
    Aceita apenas: PDF, Word (.doc, .docx), Excel (.xls, .xlsx), PowerPoint (.ppt, .pptx)
    Tamanho máximo: 10MB por arquivo
    """
    # Limites (podem ser promovidos para settings por tier futuramente)
    MAX_FILE_SIZE = getattr(settings, "PLANNING_ATTACHMENT_MAX_FILE_SIZE", 10 * 1024 * 1024)  # 10MB padrão
    MAX_FILES_PER_STUDENT = getattr(settings, "PLANNING_ATTACHMENT_MAX_FILES_PER_STUDENT", 60)
    MAX_TOTAL_BYTES_PER_STUDENT = getattr(settings, "PLANNING_ATTACHMENT_MAX_TOTAL_BYTES_PER_STUDENT", 120 * 1024 * 1024)  # 120MB
    ALLOWED_EXTENSIONS = [
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.odt', '.ods', '.odp',
        '.mp3', '.m4a', '.wav', '.ogg', '.mp4', '.webm', '.mov',
    ]
    
    try:
        plan = LessonPlan.objects.select_related('student', 'student__user', 'student__user__profile').get(id=plan_id)
        
        # Verificar permissão: usuário deve ser dono do planejamento ou admin
        try:
            is_admin = request.user.profile.is_admin
        except UserProfile.DoesNotExist:
            is_admin = False
        
        if not is_admin:
            try:
                user_profile = request.user.profile.user_profile
                if user_profile == UserProfile.PROFILE_TEACHER:
                    # Prof. dono pode anexar em qualquer planejamento dos seus alunos (mantém histórico)
                    if plan.student.user_id != request.user.id:
                        return Response(
                            {'error': 'Você não tem permissão para anexar arquivos neste planejamento.'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                elif user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                    # Parceiro só pode anexar em planejamentos seus OU de alunos atribuídos a ele
                    can_attach = (
                        (plan.user_id == request.user.id or plan.student.assigned_teacher_id == request.user.id) and
                        plan.student.user.profile.partner_teachers.filter(user=request.user).exists()
                    )
                    if not can_attach:
                        return Response(
                            {'error': 'Você não tem permissão para anexar arquivos neste planejamento.'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                else:
                    if plan.user_id != request.user.id:
                        return Response(
                            {'error': 'Você não tem permissão para anexar arquivos neste planejamento.'},
                            status=status.HTTP_403_FORBIDDEN
                        )
            except UserProfile.DoesNotExist:
                if plan.user_id != request.user.id:
                    return Response(
                        {'error': 'Você não tem permissão para anexar arquivos neste planejamento.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
        
        if 'file' not in request.FILES:
            return Response(
                {'error': 'Nenhum arquivo enviado.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        original_filename = file.name
        
        # Validar extensão
        import os
        ext = os.path.splitext(original_filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return Response(
                {'error': f'Tipo de arquivo não permitido. Permitidos: {", ".join(ALLOWED_EXTENSIONS)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar tamanho
        if file.size > MAX_FILE_SIZE:
            return Response(
                {'error': f'Arquivo muito grande. Tamanho máximo: {int(MAX_FILE_SIZE / (1024*1024))}MB'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar limites por aluno (anti-abuso): quantidade e total armazenado
        from django.db.models import Sum
        existing = LessonPlanAttachment.objects.filter(lesson_plan__student=plan.student)
        existing_count = existing.count()
        if existing_count >= MAX_FILES_PER_STUDENT:
            return Response(
                {'error': f'Limite de arquivos atingido para este aluno ({MAX_FILES_PER_STUDENT}). Remova anexos antigos para continuar.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        existing_bytes = existing.aggregate(total=Sum('file_size')).get('total') or 0
        if (existing_bytes + file.size) > MAX_TOTAL_BYTES_PER_STUDENT:
            remaining = max(0, MAX_TOTAL_BYTES_PER_STUDENT - existing_bytes)
            return Response(
                {'error': f'Limite de armazenamento atingido para este aluno. Restante: {int(remaining / (1024*1024))}MB.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Criar anexo
        attachment = LessonPlanAttachment.objects.create(
            lesson_plan=plan,
            file=file,
            original_filename=original_filename,
            file_size=file.size
        )
        display_title = (request.POST.get("display_title") or "").strip()
        if display_title:
            import re
            base = re.sub(r"[^\w\s\-.àáâãéêíóôõúçÀÁÂÃÉÊÍÓÔÕÚÇ]", "", display_title).strip()[:180]
            if base:
                attachment.original_filename = base + ext
                attachment.save()

        serializer = LessonPlanAttachmentSerializer(attachment, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except LessonPlan.DoesNotExist:
        return Response(
            {'error': 'Planejamento não encontrado.'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Erro ao fazer upload: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_planning_attachment(request, attachment_id):
    """Deleta um anexo de planejamento"""
    try:
        attachment = LessonPlanAttachment.objects.select_related(
            'lesson_plan', 'lesson_plan__student', 'lesson_plan__student__user', 'lesson_plan__student__user__profile'
        ).get(id=attachment_id)
        plan = attachment.lesson_plan
        
        # Verificar permissão
        try:
            is_admin = request.user.profile.is_admin
        except UserProfile.DoesNotExist:
            is_admin = False
        
        if not is_admin:
            try:
                user_profile = request.user.profile.user_profile
                if user_profile == UserProfile.PROFILE_TEACHER:
                    if plan.student.user_id != request.user.id:
                        return Response(
                            {'error': 'Você não tem permissão para excluir este anexo.'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                elif user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                    can_delete = (
                        (plan.user_id == request.user.id or plan.student.assigned_teacher_id == request.user.id) and
                        plan.student.user.profile.partner_teachers.filter(user=request.user).exists()
                    )
                    if not can_delete:
                        return Response(
                            {'error': 'Você não tem permissão para excluir este anexo.'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                else:
                    if plan.user_id != request.user.id:
                        return Response(
                            {'error': 'Você não tem permissão para excluir este anexo.'},
                            status=status.HTTP_403_FORBIDDEN
                        )
            except UserProfile.DoesNotExist:
                if plan.user_id != request.user.id:
                    return Response(
                        {'error': 'Você não tem permissão para excluir este anexo.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
        
        # Deletar arquivo físico
        if attachment.file:
            attachment.file.delete()
        
        attachment.delete()
        return Response({'success': True}, status=status.HTTP_200_OK)
        
    except LessonPlanAttachment.DoesNotExist:
        return Response(
            {'error': 'Anexo não encontrado.'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Erro ao excluir anexo: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("student").all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Prof. Parceiro não pode acessar Cobrança
        try:
            user_profile = self.request.user.profile.user_profile
            if user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                return Invoice.objects.none()
        except UserProfile.DoesNotExist:
            pass
        
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

    def create(self, request, *args, **kwargs):
        # Bloqueia criação para Prof. Parceiro
        try:
            user_profile = request.user.profile.user_profile
            if user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                return Response(
                    {'error': 'Professores parceiros não podem criar cobranças'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except UserProfile.DoesNotExist:
            pass
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        # Bloqueia edição para Prof. Parceiro
        try:
            user_profile = request.user.profile.user_profile
            if user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                return Response(
                    {'error': 'Professores parceiros não podem editar cobranças'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except UserProfile.DoesNotExist:
            pass
        return super().update(request, *args, **kwargs)


def get_financial_entries_queryset_for_user(request):
    """
    Retorna o queryset de FinancialEntry filtrado igual à tela de financeiro.
    Usado pelo dashboard e outras views para garantir consistência.
    """
    qs = FinancialEntry.objects.select_related("student", "user", "beneficiary_user")
    try:
        is_admin = request.user.profile.is_admin
        user_profile = request.user.profile.user_profile
    except UserProfile.DoesNotExist:
        is_admin = False
        user_profile = None

    if not is_admin:
        if user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
            qs = qs.filter(student__user__profile__partner_teachers=request.user.profile).filter(
                student__assigned_teacher=request.user
            ).filter(Q(user=request.user) | Q(beneficiary_user=request.user)).distinct()
        elif user_profile == UserProfile.PROFILE_TEACHER:
            qs = qs.filter(student__user=request.user)
        else:
            qs = qs.filter(user=request.user)
    return qs


class FinancialEntryViewSet(viewsets.ModelViewSet):
    queryset = FinancialEntry.objects.select_related("student", "user", "beneficiary_user").all()
    serializer_class = FinancialEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = get_financial_entries_queryset_for_user(self.request)
        today = date.today()

        # Filtro "somente vencidos": todos os lançamentos em atraso (qualquer mês)
        overdue_only = self.request.query_params.get("overdue_only", "").lower() in ("1", "true", "yes")
        if overdue_only:
            qs = qs.filter(
                due_date__lt=today,
                status__in=(FinancialEntry.STATUS_PENDING, FinancialEntry.STATUS_OVERDUE)
            ).order_by("due_date")
            return qs

        # Filtro por mês - mostra lançamentos com vencimento no mês (baseado na data de vencimento)
        month_param = self.request.query_params.get("month")
        if month_param:
            try:
                year, month = map(int, month_param.split("-"))
                # Mostra lançamentos que têm vencimento no mês especificado
                qs = qs.filter(due_date__year=year, due_date__month=month)
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

    def create(self, request, *args, **kwargs):
        # Bloqueia criação para Prof. Parceiro
        try:
            user_profile = request.user.profile.user_profile
            if user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                return Response(
                    {'error': 'Professores parceiros não podem criar lançamentos financeiros'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except UserProfile.DoesNotExist:
            pass
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        # Bloqueia edição para Prof. Parceiro
        try:
            user_profile = request.user.profile.user_profile
            if user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                return Response(
                    {'error': 'Professores parceiros não podem editar lançamentos financeiros'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except UserProfile.DoesNotExist:
            pass
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        # Um único campo "Professor responsável": define quem é responsável e quem recebe o lançamento
        assigned_user = serializer.validated_data.get('user')
        if not assigned_user:
            assigned_user = self.request.user
        beneficiary_user = serializer.validated_data.get('beneficiary_user') or assigned_user
        serializer.save(user=assigned_user, beneficiary_user=beneficiary_user)
    
    @action(detail=True, methods=['get'])
    def billing_data(self, request, pk=None):
        """Retorna dados formatados para a tela de cobrança baseado no lançamento financeiro"""
        entry = self.get_object()
        student = entry.student
        
        # Calcula dias em atraso
        days_overdue = 0
        status_color = "🟢"
        status_text = "Pago"
        
        if entry.status == FinancialEntry.STATUS_OVERDUE:
            days_overdue = (date.today() - entry.due_date).days
            status_color = "🔴"
            status_text = "Vencido"
        elif entry.status == FinancialEntry.STATUS_PENDING:
            if entry.due_date == date.today():
                status_color = "🟡"
                status_text = "Vence hoje"
            elif entry.due_date > date.today():
                status_color = "🟢"
                status_text = "Pendente"
            else:
                days_overdue = (date.today() - entry.due_date).days
                status_color = "🔴"
                status_text = "Vencido"
        elif entry.status == FinancialEntry.STATUS_PAID:
            status_color = "🟢"
            status_text = "Pago"
        
        # Busca histórico de cobranças
        billing_logs = BillingLog.objects.filter(financial_entry=entry).order_by('-sent_at')
        logs_serializer = BillingLogSerializer(billing_logs, many=True, context={'request': request})
        
        # Progresso real: aulas realizadas (Lesson.realized=True) - igual ao cadastro do aluno
        lessons_done = Lesson.objects.filter(student=student, realized=True).count()
        
        # Formata dados do aluno
        student_data = {
            'id': student.id,
            'name': student.name,
            'phone': student.phone or '',
            'email': student.email or '',
            'plan_name': student.plan_name or '',
            'status': student.status or 'active',
            'lessons_total': student.lessons_total,
            'lessons_done': lessons_done,
            'pix_key': student.pix_key or '',
            'default_due_day': student.default_due_day,
            'preferred_payment_method': student.preferred_payment_method or '',
        }
        
        # Formata dados do lançamento
        entry_data = {
            'id': entry.id,
            'description': entry.description,
            'amount': float(entry.amount),
            'due_date': entry.due_date.isoformat() if entry.due_date else None,
            'issue_date': entry.issue_date.isoformat() if entry.issue_date else None,
            'status': entry.status,
            'current_installment': entry.current_installment,
            'installments': entry.installments,
            'payment_method': entry.payment_method or '',
        }
        
        return Response({
            'student': student_data,
            'entry': entry_data,
            'status': {
                'color': status_color,
                'text': status_text,
                'days_overdue': days_overdue,
            },
            'billing_logs': logs_serializer.data,
        })


# ==========================
# Autenticação
# ==========================

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def login_view(request):
    """View para fazer login"""
    # GET: apenas retorna sucesso para obter CSRF token
    if request.method == 'GET':
        return Response({'message': 'CSRF token disponível'}, status=status.HTTP_200_OK)
    
    # POST: processa login
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {'error': 'Username e senha são obrigatórios'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = authenticate(request, username=username, password=password)
    
    if user is not None:
        if user.is_active:
            login(request, user)
            # Força salvar a sessão
            request.session.save()
            # Obtém informações do perfil
            try:
                is_admin = user.profile.is_admin
                user_profile = user.profile.user_profile
            except UserProfile.DoesNotExist:
                is_admin = False
                user_profile = None
            
            return Response({
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_admin': is_admin,
                    'user_profile': user_profile,
                }
            })
        else:
            return Response(
                {'error': 'Usuário inativo'},
                status=status.HTTP_403_FORBIDDEN
            )
    else:
        return Response(
            {'error': 'Credenciais inválidas'},
            status=status.HTTP_401_UNAUTHORIZED
        )


@api_view(['POST'])
@permission_classes([AllowAny])  # Permite logout mesmo sem autenticação (para limpar sessão)
def logout_view(request):
    """View para fazer logout"""
    logout(request)
    return Response({'success': True})


@api_view(['GET'])
@permission_classes([AllowAny])  # Permite verificar sem autenticação para retornar erro apropriado
def current_user_view(request):
    """View para obter informações do usuário atual"""
    if not request.user.is_authenticated:
        return Response(
            {'error': 'Não autenticado'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    user = request.user
    try:
        is_admin = user.profile.is_admin
        user_profile = user.profile.user_profile
        welcome_dismissed_forever = getattr(user.profile, 'welcome_dismissed_forever', False)
    except UserProfile.DoesNotExist:
        is_admin = False
        user_profile = None
        welcome_dismissed_forever = False
    
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_admin': is_admin,
        'user_profile': user_profile,
        'welcome_dismissed_forever': welcome_dismissed_forever,
    })


class LessonPlanViewSet(viewsets.ModelViewSet):
    queryset = LessonPlan.objects.select_related("student", "user").all().order_by("-date", "student__name")
    serializer_class = LessonPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Admin vê todos os lesson plans, usuários normais veem apenas os seus
        try:
            is_admin = self.request.user.profile.is_admin
        except UserProfile.DoesNotExist:
            is_admin = False
        
        if not is_admin:
            try:
                user_profile = self.request.user.profile.user_profile
                if user_profile == UserProfile.PROFILE_TEACHER:
                    # Prof. Principal vê todos os planejamentos dos seus alunos (mantém histórico mesmo após desvincular parceiro)
                    queryset = queryset.filter(student__user=self.request.user)
                elif user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                    # Parceiro só vê: (1) planejamentos que ele criou OU (2) planejamentos feitos para alunos atribuídos a ele
                    queryset = queryset.filter(student__user__profile__partner_teachers=self.request.user.profile).filter(
                        Q(user=self.request.user) | Q(student__assigned_teacher=self.request.user)
                    )
                else:
                    # Outros usuários veem apenas os seus
                    queryset = queryset.filter(user=self.request.user)
            except UserProfile.DoesNotExist:
                queryset = queryset.filter(user=self.request.user)
        
        student_id = self.request.query_params.get('student', None)
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        return queryset

    def _get_assignable_user_ids(self):
        """IDs de usuários que o professor principal pode atribuir (ele mesmo ou parceiros)."""
        try:
            profile = self.request.user.profile
            if profile.user_profile == UserProfile.PROFILE_TEACHER:
                partner_ids = list(profile.partner_teachers.values_list("user_id", flat=True))
                return [self.request.user.id] + partner_ids
        except UserProfile.DoesNotExist:
            pass
        return [self.request.user.id]

    def perform_create(self, serializer):
        student = serializer.validated_data.get('student')
        if not student:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"student": "Selecione um aluno."})
        try:
            profile = self.request.user.profile.user_profile
            if profile == UserProfile.PROFILE_PARTNER_TEACHER:
                if student.assigned_teacher_id != self.request.user.id:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied("Você só pode criar planejamento para alunos atribuídos a você.")
                # Parceiro sempre salva como ele mesmo
                target_user = self.request.user
            elif profile == UserProfile.PROFILE_TEACHER:
                if student.user_id != self.request.user.id:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied("Este aluno não pertence à sua conta.")
                # Dono pode escolher professor (ele ou parceiro) via payload
                user_id = self.request.data.get("user")
                if user_id is not None:
                    try:
                        uid = int(user_id)
                        if uid in self._get_assignable_user_ids():
                            target_user = User.objects.get(pk=uid)
                            # Dono atribuindo a parceiro: aluno deve estar vinculado ao parceiro
                            if target_user.id != self.request.user.id:
                                if student.assigned_teacher_id != target_user.id:
                                    from rest_framework.exceptions import ValidationError
                                    raise ValidationError({
                                        "student_assignment": "O aluno não está vinculado a este professor parceiro. Atribua o aluno ao professor na tela de Alunos antes de criar o planejamento.",
                                        "student_name": getattr(student, "name", "este aluno"),
                                        "teacher_name": target_user.get_full_name() or target_user.username,
                                    })
                        else:
                            from rest_framework.exceptions import PermissionDenied
                            raise PermissionDenied("Só é possível atribuir a você ou a seus professores parceiros.")
                    except (ValueError, User.DoesNotExist):
                        target_user = self.request.user
                else:
                    target_user = self.request.user
            else:
                target_user = self.request.user
        except UserProfile.DoesNotExist:
            if student.user_id != self.request.user.id:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Este aluno não pertence à sua conta.")
            target_user = self.request.user
        serializer.save(user=target_user)

    def perform_update(self, serializer):
        """Permite ao dono da conta alterar o professor responsável (ele ou parceiro)."""
        instance = serializer.instance
        try:
            profile = self.request.user.profile.user_profile
            if profile == UserProfile.PROFILE_PARTNER_TEACHER:
                # Parceiro não pode alterar o professor - mantém como está
                serializer.save()
                return
            if profile == UserProfile.PROFILE_TEACHER:
                user_id = self.request.data.get("user")
                if user_id is not None:
                    try:
                        uid = int(user_id)
                        if uid in self._get_assignable_user_ids():
                            target_user = User.objects.get(pk=uid)
                            student = instance.student
                            if target_user.id != self.request.user.id and student.assigned_teacher_id != target_user.id:
                                from rest_framework.exceptions import ValidationError
                                raise ValidationError({
                                    "student_assignment": "O aluno não está vinculado a este professor parceiro. Atribua o aluno ao professor na tela de Alunos antes de salvar.",
                                    "student_name": getattr(student, "name", "este aluno"),
                                    "teacher_name": target_user.get_full_name() or target_user.username,
                                })
                            serializer.save(user=target_user)
                            return
                        else:
                            from rest_framework.exceptions import PermissionDenied
                            raise PermissionDenied("Só é possível atribuir a você ou a seus professores parceiros.")
                    except (ValueError, User.DoesNotExist):
                        pass
        except UserProfile.DoesNotExist:
            pass
        serializer.save()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


def _planning_user_ids(request):
    """IDs de usuários cujos planejamentos o request.user pode ver (igual LessonPlanViewSet)."""
    try:
        is_admin = request.user.profile.is_admin
    except UserProfile.DoesNotExist:
        is_admin = False
    if is_admin:
        return None  # vê todos
    try:
        profile = request.user.profile.user_profile
        if profile == UserProfile.PROFILE_TEACHER:
            partner_ids = list(request.user.profile.partner_teachers.values_list("user_id", flat=True))
            partner_ids.append(request.user.id)
            return partner_ids
        return [request.user.id]
    except UserProfile.DoesNotExist:
        return [request.user.id]


def _planning_date_range(period, start_date_str, end_date_str, tz_date):
    """Retorna (start_date, end_date) para o período. tz_date = date em timezone do usuário."""
    today = tz_date

    if period == "today":
        return today, today

    if period == "next7":
        end = today + timedelta(days=6)
        return today, end

    if period == "week":
        # semana atual: domingo a sábado
        wd = today.weekday()
        sunday = today - timedelta(days=(wd + 1) % 7)
        if wd == 6:
            sunday = today
        saturday = sunday + timedelta(days=6)
        return sunday, saturday

    if period == "nextweek":
        wd = today.weekday()
        sunday = today - timedelta(days=(wd + 1) % 7)
        if wd == 6:
            next_sun = today + timedelta(days=7)
        else:
            next_sun = sunday + timedelta(days=7)
        return next_sun, next_sun + timedelta(days=6)

    if period == "month":
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return start, end

    if period == "last90":
        start = today - timedelta(days=89)
        return start, today

    if period == "custom" and start_date_str and end_date_str:
        try:
            start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            if start <= end:
                return start, end
        except ValueError:
            pass
    return today, today + timedelta(days=6)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def planning_list_api(request):
    """
    GET /api/planning/list/
    Params: period (today|next7|week|nextweek|month|last90|custom),
            start_date, end_date (quando custom),
            student_id, status (all|incomplete|no_goals|no_materials|ok), q (busca).
    Retorna JSON: period_label, total, days[], students[].
    """
    from collections import defaultdict
    from zoneinfo import ZoneInfo
    now = timezone.now()
    # Usar timezone do usuário para calcular "hoje" corretamente
    # Servidor em UTC + usuário no Brasil = "hoje" errado (ex: 22h BR já é dia seguinte em UTC)
    try:
        tz_str = getattr(request.user.profile, "timezone", None) or "America/Sao_Paulo"
        user_tz = ZoneInfo(tz_str)
    except Exception:
        user_tz = ZoneInfo("America/Sao_Paulo")
    tz_date = now.astimezone(user_tz).date()

    period = (request.GET.get("period") or "next7").strip().lower()
    start_date_str = request.GET.get("start_date", "").strip()
    end_date_str = request.GET.get("end_date", "").strip()
    student_id = request.GET.get("student_id", "").strip()
    teacher_id = request.GET.get("teacher_id", "").strip()  # Filtrar por professor (dono da conta: self ou parceiro)
    status_filter = (request.GET.get("status") or "all").strip().lower()
    q_search = (request.GET.get("q") or "").strip()

    start_date, end_date = _planning_date_range(period, start_date_str, end_date_str, tz_date)

    period_labels = {
        "today": "Hoje",
        "next7": "Próximos 7 dias",
        "last90": "Últimos 90 dias",
        "week": "Esta semana",
        "nextweek": "Próxima semana",
        "month": "Este mês",
        "custom": "Custom",
    }
    period_label = period_labels.get(period, "Próximos 7 dias")

    qs = LessonPlan.objects.select_related("student", "user").order_by("date", "student__name")
    user_ids = _planning_user_ids(request)
    try:
        profile = request.user.profile.user_profile
        if profile == UserProfile.PROFILE_TEACHER:
            # Prof. Principal vê todos os planejamentos dos seus alunos (mantém histórico mesmo após desvincular parceiro)
            qs = qs.filter(student__user=request.user)
        elif profile == UserProfile.PROFILE_PARTNER_TEACHER:
            # Parceiro só vê planejamentos que criou OU feitos para alunos atribuídos a ele
            qs = qs.filter(student__user__profile__partner_teachers=request.user.profile).filter(
                Q(user=request.user) | Q(student__assigned_teacher=request.user)
            )
        elif user_ids is not None:
            qs = qs.filter(user_id__in=user_ids)
    except UserProfile.DoesNotExist:
        if user_ids is not None:
            qs = qs.filter(user_id__in=user_ids)
    # Filtro por professor (dono da conta: filtrar por "eu" ou "parceiro X" para ver só planejamentos de um responsável)
    if teacher_id and teacher_id != "all":
        try:
            tid = int(teacher_id)
            if user_ids is not None and tid in user_ids:
                qs = qs.filter(user_id=tid)
        except ValueError:
            pass
    qs = qs.filter(date__gte=start_date, date__lte=end_date)

    if student_id and student_id != "all":
        try:
            qs = qs.filter(student_id=int(student_id))
        except ValueError:
            pass

    if q_search:
        qs = qs.filter(
            Q(student__name__icontains=q_search) | Q(goals__icontains=q_search)
        )

    if status_filter and status_filter != "all":
        if status_filter == "no_goals":
            qs = qs.filter(Q(goals__isnull=True) | Q(goals=""))
        elif status_filter == "no_materials":
            qs = qs.filter(Q(links__isnull=True) | Q(links=""))
        elif status_filter == "incomplete":
            qs = qs.filter(
                Q(Q(goals__isnull=True) | Q(goals="")) |
                Q(Q(links__isnull=True) | Q(links=""))
            )
        elif status_filter == "ok":
            qs = qs.exclude(Q(goals__isnull=True) | Q(goals=""))
            qs = qs.exclude(Q(links__isnull=True) | Q(links=""))

    plans = list(qs)

    # Lista de alunos para o filtro: mesmo critério do cadastro (dono vê os seus; parceiro só vê de donos que ainda o têm vinculado)
    students_qs = Student.objects.order_by("name")
    try:
        profile = request.user.profile.user_profile
        if profile == UserProfile.PROFILE_PARTNER_TEACHER:
            students_qs = students_qs.filter(user__profile__partner_teachers=request.user.profile).filter(assigned_teacher=request.user)
        elif profile == UserProfile.PROFILE_TEACHER:
            students_qs = students_qs.filter(user=request.user)
        elif user_ids is not None:
            students_qs = students_qs.filter(user_id__in=user_ids)
    except UserProfile.DoesNotExist:
        students_qs = students_qs.filter(user=request.user)
    students = [{"id": s.id, "name": s.name} for s in students_qs]

    def goals_preview(txt, max_len=80):
        if not txt or not txt.strip():
            return ""
        t = txt.strip().replace("\n", " ")[:max_len]
        return t + "…" if len(txt.strip()) > max_len else t

    def links_to_materials(links_str):
        def normalize_url(url):
            """Normaliza URL para garantir que seja absoluta"""
            if not url or url == "#":
                return "#"
            url = url.strip()
            # Se já começa com http:// ou https://, retorna como está
            if url.startswith("http://") or url.startswith("https://"):
                return url
            # Se começa com //, adiciona https:
            if url.startswith("//"):
                return "https:" + url
            # Se não começa com /, assume que é um domínio e adiciona https://
            if not url.startswith("/"):
                return "https://" + url
            # URLs relativas começando com / são mantidas (podem ser links internos)
            return url
        
        out = []
        if not links_str or not links_str.strip():
            return out
        for raw in links_str.strip().split("\n"):
            url = raw.strip()
            if not url:
                continue
            # Normaliza a URL
            url = normalize_url(url)
            title = "Link"
            if "docs.google.com" in url or "slides" in url.lower():
                title = "Google Slides"
            elif "docs.google.com" in url or "document" in url.lower():
                title = "Google Doc"
            elif "youtube.com" in url or "youtu.be" in url:
                title = "YouTube"
            out.append({"title": title, "url": url})
        return out

    by_date = defaultdict(list)
    for p in plans:
        has_goals = bool(p.goals and p.goals.strip())
        has_materials = bool(p.links and p.links.strip())
        materials = links_to_materials(p.links or "")
        teacher_name = (p.user.get_full_name() or p.user.username) if p.user_id else ""
        by_date[p.date].append({
            "id": p.id,
            "student": {"id": p.student_id, "name": p.student.name},
            "teacher": {"id": p.user_id, "name": teacher_name},
            "date": p.date.strftime("%Y-%m-%d"),
            "time": None,
            "duration_min": None,
            "goals": goals_preview(p.goals or ""),
            "goals_raw": (p.goals or "").strip(),
            "materials": materials,
            "status": {"has_goals": has_goals, "has_materials": has_materials},
        })

    _WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
    _MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

    def _date_label(dt):
        wd = _WEEKDAYS[dt.weekday()]
        m = _MONTHS[dt.month - 1]
        return f"{wd}, {dt.day} de {m} de {dt.year}"

    today_plus_6 = tz_date + timedelta(days=6)
    days = []
    d = start_date
    while d <= end_date:
        items = by_date.get(d, [])
        if not items:
            d += timedelta(days=1)
            continue
        weekday_label = _WEEKDAYS[d.weekday()]
        label = _date_label(d)
        is_open = (d >= tz_date) and (d <= today_plus_6)
        days.append({
            "date": d.strftime("%Y-%m-%d"),
            "weekday_label": weekday_label,
            "label": label,
            "count": len(items),
            "is_open": is_open,
            "items": items,
        })
        d += timedelta(days=1)

    total = sum(g["count"] for g in days)
    return Response({
        "period_label": period_label,
        "total": total,
        "days": days,
        "students": students,
    })


class BillingLogViewSet(viewsets.ModelViewSet):
    queryset = BillingLog.objects.select_related("financial_entry", "financial_entry__student", "user").all()
    serializer_class = BillingLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        
        # Filtro por lançamento financeiro específico
        financial_entry_id = self.request.query_params.get("financial_entry")
        if financial_entry_id:
            qs = qs.filter(financial_entry_id=financial_entry_id)
        
        # Usuário só vê seus próprios logs ou logs de lançamentos que pode ver
        try:
            is_admin = user.profile.is_admin
            user_profile = user.profile.user_profile
        except UserProfile.DoesNotExist:
            is_admin = False
            user_profile = None

        if not is_admin:
            if user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                # Prof. Parceiro vê apenas logs de lançamentos de alunos ATRIBUÍDOS a ele
                qs = qs.filter(financial_entry__student__assigned_teacher=user).filter(
                    Q(financial_entry__beneficiary_user=user) | Q(financial_entry__user=user)
                )
            elif user_profile == UserProfile.PROFILE_TEACHER:
                # Prof. Principal vê logs de seus lançamentos e dos parceiros
                partner_ids = list(user.profile.partner_teachers.values_list('user_id', flat=True))
                partner_ids.append(user.id)
                qs = qs.filter(
                    Q(financial_entry__user_id__in=partner_ids) | 
                    Q(financial_entry__beneficiary_user_id__in=partner_ids)
                )
            else:
                qs = qs.filter(user=user)
        
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class StudentHomeworkViewSet(viewsets.ModelViewSet):
    queryset = StudentHomework.objects.select_related("student", "assigned_by", "student__user", "student__assigned_teacher").prefetch_related("messages").all()
    serializer_class = StudentHomeworkSerializer
    permission_classes = [IsAuthenticated]

    def _students_queryset_for_request(self):
        """Mesma regra do detalhe do aluno / StudentViewSet (dono, parceiro, admin)."""
        qs = Student.objects.select_related("user", "assigned_teacher").all()
        try:
            is_admin = self.request.user.profile.is_admin
            user_profile = self.request.user.profile.user_profile
        except UserProfile.DoesNotExist:
            is_admin = False
            user_profile = None
        if is_admin:
            return qs
        if user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
            return qs.filter(user__profile__partner_teachers=self.request.user.profile).filter(assigned_teacher=self.request.user)
        return qs.filter(user=self.request.user)

    def get_queryset(self):
        students_qs = self._students_queryset_for_request()
        qs = super().get_queryset().filter(student__in=students_qs)
        student_id = self.request.query_params.get("student")
        if student_id:
            qs = qs.filter(student_id=student_id)
        status_q = self.request.query_params.get("status")
        if status_q:
            qs = qs.filter(status=status_q)
        return qs.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        """
        Mantém as mensagens como "não lidas" até o professor abrir a conversa
        (acionado pelo endpoint mark-read na expansão do card).
        """
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)

    @action(detail=True, methods=["POST"], permission_classes=[IsAuthenticated])
    def messages(self, request, pk=None):
        hw = self.get_object()
        text = (request.data.get("message") or "").strip()
        if not text:
            return Response({"detail": "Mensagem vazia."}, status=status.HTTP_400_BAD_REQUEST)
        msg = StudentHomeworkMessage.objects.create(
            homework=hw,
            sender=StudentHomeworkMessage.SENDER_TEACHER,
            message=text,
            created_by=request.user,
        )

        # Mantém compatibilidade com campo legado.
        hw.teacher_feedback = text
        hw.save(update_fields=["teacher_feedback", "updated_at"])

        return Response(
            {
                "id": msg.id,
                "sender": msg.sender,
                "sender_label": "Professor",
                "message": msg.message,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["POST"], permission_classes=[IsAuthenticated], url_path="mark-read")
    def mark_read(self, request, pk=None):
        """
        Marca as mensagens do aluno (sender=student) desta tarefa como lidas
        para o professor logado.
        """
        hw = self.get_object()
        user = request.user

        unread_msg_ids_qs = (
            StudentHomeworkMessage.objects.filter(
                homework=hw,
                sender=StudentHomeworkMessage.SENDER_STUDENT,
            ).exclude(reads__user=user)
            .values_list("id", flat=True)
        )
        msg_ids = list(unread_msg_ids_qs[:1000])
        if msg_ids:
            read_objs = [
                StudentHomeworkMessageRead(message_id=mid, user=user) for mid in msg_ids
            ]
            StudentHomeworkMessageRead.objects.bulk_create(read_objs, ignore_conflicts=True)

        return Response({"ok": True, "marked": len(msg_ids)}, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet para gerenciar usuários (apenas admins)"""
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Apenas admins podem ver a lista de usuários
        user = self.request.user
        try:
            if not user.profile.is_admin:
                return User.objects.none()
        except UserProfile.DoesNotExist:
            return User.objects.none()
        return super().get_queryset()
    
    def create(self, request, *args, **kwargs):
        # Verifica se é admin
        user = request.user
        try:
            if not user.profile.is_admin:
                return Response(
                    {'error': 'Apenas administradores podem criar usuários'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except UserProfile.DoesNotExist:
            return Response(
                {'error': 'Apenas administradores podem criar usuários'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        # Verifica se é admin
        user = request.user
        try:
            if not user.profile.is_admin:
                return Response(
                    {'error': 'Apenas administradores podem editar usuários'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except UserProfile.DoesNotExist:
            return Response(
                {'error': 'Apenas administradores podem editar usuários'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        # Verifica se é admin
        user = request.user
        try:
            if not user.profile.is_admin:
                return Response(
                    {'error': 'Apenas administradores podem excluir usuários'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except UserProfile.DoesNotExist:
            return Response(
                {'error': 'Apenas administradores podem excluir usuários'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


# ==========================
# Stripe Subscription Flow
# ==========================

# Configurar Stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
    """
    Cria uma Stripe Checkout Session para assinatura.
    Requer autenticação e plano válido.
    Formato esperado: {'tier': 'basic|premium|platinum', 'plan': 'monthly|semestral|annual'}
    """
    tier = request.data.get('tier', '').strip().lower()
    plan = request.data.get('plan', '').strip().lower()
    
    # Validar tier
    if tier not in [Subscription.TIER_BASIC, Subscription.TIER_PREMIUM, Subscription.TIER_PLATINUM]:
        return Response(
            {'error': 'Tier inválido. Use: basic, premium ou platinum'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validar periodicidade
    if plan not in [Subscription.PLAN_MONTHLY, Subscription.PLAN_SEMESTRAL, Subscription.PLAN_ANNUAL]:
        return Response(
            {'error': 'Periodicidade inválida. Use: monthly, semestral ou annual'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Mapeamento de planos para price IDs do Stripe
    # IMPORTANTE: Configure estes IDs no seu painel do Stripe
    # Formato: STRIPE_PRICE_ID_{TIER}_{PLAN} (ex: STRIPE_PRICE_ID_BASIC_MONTHLY)
    PLAN_PRICE_IDS = {
        f"{Subscription.TIER_BASIC}_{Subscription.PLAN_MONTHLY}": os.environ.get("STRIPE_PRICE_ID_BASIC_MONTHLY", ""),
        f"{Subscription.TIER_BASIC}_{Subscription.PLAN_SEMESTRAL}": os.environ.get("STRIPE_PRICE_ID_BASIC_SEMESTRAL", ""),
        f"{Subscription.TIER_BASIC}_{Subscription.PLAN_ANNUAL}": os.environ.get("STRIPE_PRICE_ID_BASIC_ANNUAL", ""),
        f"{Subscription.TIER_PREMIUM}_{Subscription.PLAN_MONTHLY}": os.environ.get("STRIPE_PRICE_ID_PREMIUM_MONTHLY", ""),
        f"{Subscription.TIER_PREMIUM}_{Subscription.PLAN_SEMESTRAL}": os.environ.get("STRIPE_PRICE_ID_PREMIUM_SEMESTRAL", ""),
        f"{Subscription.TIER_PREMIUM}_{Subscription.PLAN_ANNUAL}": os.environ.get("STRIPE_PRICE_ID_PREMIUM_ANNUAL", ""),
        f"{Subscription.TIER_PLATINUM}_{Subscription.PLAN_MONTHLY}": os.environ.get("STRIPE_PRICE_ID_PLATINUM_MONTHLY", ""),
        f"{Subscription.TIER_PLATINUM}_{Subscription.PLAN_SEMESTRAL}": os.environ.get("STRIPE_PRICE_ID_PLATINUM_SEMESTRAL", ""),
        f"{Subscription.TIER_PLATINUM}_{Subscription.PLAN_ANNUAL}": os.environ.get("STRIPE_PRICE_ID_PLATINUM_ANNUAL", ""),
    }
    
    plan_key = f"{tier}_{plan}"
    price_id = PLAN_PRICE_IDS.get(plan_key)
    if not price_id:
        return Response(
            {'error': f'Price ID não configurado para o plano {tier} {plan}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Verificar se o plano escolhido comporta os dados atuais (ex: trial com 20 alunos → Basic não cabe)
    # Conta apenas alunos ATIVOS (pausados/encerrados não entram no limite)
    user = request.user
    if tier == Subscription.TIER_BASIC:
        student_count = Student.objects.filter(user=user, status=Student.STATUS_ACTIVE).count()
        if student_count > 15:
            return Response(
                {'error': f'Você tem {student_count} alunos ativos. O plano Basic permite até 15. '
                         'Escolha Premium ou Platinum para manter todos.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    elif tier == Subscription.TIER_PREMIUM:
        try:
            partner_count = user.profile.partner_teachers.count()
            if partner_count > 2:
                return Response(
                    {'error': f'Você tem {partner_count} professores parceiros. O plano Premium permite até 2. '
                             'Escolha Platinum para manter todos.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except UserProfile.DoesNotExist:
            pass

    # URLs de retorno
    base_url = request.build_absolute_uri('/')[:-1]  # Remove trailing slash
    success_url = f"{base_url}/payment-processing/?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/planos/"
    
    try:
        # Criar ou obter customer no Stripe
        customer_id = None
        subscription = getattr(request.user, 'subscription', None)
        if subscription and subscription.stripe_customer_id:
            customer_id = subscription.stripe_customer_id
        else:
            # Criar customer no Stripe
            customer = stripe.Customer.create(
                email=request.user.email or None,
                metadata={
                    'user_id': str(request.user.id),
                    'username': request.user.username,
                }
            )
            customer_id = customer.id
            
            # Criar ou atualizar subscription local
            if not subscription:
                subscription = Subscription.objects.create(
                    user=request.user,
                    tier=tier,
                    plan=plan,
                    status=Subscription.STATUS_PENDING,
                    stripe_customer_id=customer_id
                )
            else:
                subscription.tier = tier
                subscription.plan = plan
                subscription.stripe_customer_id = customer_id
                subscription.save()
        
        # Criar Checkout Session com trial de 7 dias
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(request.user.id),  # Liga a sessão ao usuário
            metadata={
                'user_id': str(request.user.id),
                'tier': tier,
                'plan': plan,
            },
            subscription_data={
                # Sem trial no Stripe: trial gratuito é gerenciado pelo sistema (trial_ends_at)
                'metadata': {
                    'user_id': str(request.user.id),
                    'tier': tier,
                    'plan': plan,
                }
            }
        )
        
        return Response({
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id
        })
        
    except stripe.error.StripeError as e:
        return Response(
            {'error': f'Erro ao criar sessão de checkout: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {'error': f'Erro inesperado: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """
    Webhook do Stripe para processar eventos de assinatura.
    Processa: checkout.session.completed, invoice.paid, invoice.payment_failed, customer.subscription.deleted
    """
    print("=" * 50)
    print("WEBHOOK RECEBIDO!")
    print("=" * 50)
    
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    
    if not webhook_secret:
        print("ERRO: Webhook secret não configurado")
        return HttpResponse("Webhook secret não configurado", status=500)
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        print(f"✅ Evento verificado: {event['id']}")
    except ValueError as e:
        print(f"ERRO: Payload inválido - {e}")
        return HttpResponse("Payload inválido", status=400)
    except stripe.error.SignatureVerificationError as e:
        print(f"ERRO: Assinatura inválida - {e}")
        return HttpResponse("Assinatura inválida", status=400)
    
    event_id = event['id']
    event_type = event['type']
    
    print(f"📦 Tipo de evento: {event_type}")
    print(f"🆔 ID do evento: {event_id}")
    
    # Verificar idempotência
    stripe_event, created = StripeEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            'event_type': event_type,
            'event_data': event,
        }
    )
    
    if not created:
        if stripe_event.processed:
            print(f"⚠️ Evento já processado anteriormente")
            return JsonResponse({'status': 'already_processed'})
        else:
            print(f"🔄 Evento já existe mas não foi processado. Processando agora...")
    
    # Processar evento
    try:
        print(f"🔄 Processando evento {event_type}...")
        
        if event_type == 'checkout.session.completed':
            print("📝 Chamando handle_checkout_session_completed...")
            handle_checkout_session_completed(event['data']['object'])
        elif event_type == 'invoice.paid' or event_type == 'invoice.payment_succeeded':
            print("📝 Chamando handle_invoice_paid...")
            handle_invoice_paid(event['data']['object'])
        elif event_type == 'invoice.payment_failed':
            print("📝 Chamando handle_invoice_payment_failed...")
            handle_invoice_payment_failed(event['data']['object'])
        elif event_type == 'customer.subscription.deleted':
            print("📝 Chamando handle_subscription_deleted...")
            handle_subscription_deleted(event['data']['object'])
        elif event_type == 'customer.subscription.updated':
            print("📝 Chamando handle_subscription_updated...")
            handle_subscription_updated(event['data']['object'])
        elif event_type == 'customer.subscription.created':
            print("📝 Chamando handle_subscription_created...")
            handle_subscription_created(event['data']['object'])
        else:
            print(f"⚠️ Tipo de evento não tratado: {event_type}")
        
        stripe_event.processed = True
        stripe_event.processed_at = timezone.now()
        stripe_event.save()
        
        print(f"✅ Evento processado com sucesso!")
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        print(f"❌ ERRO ao processar evento: {e}")
        import traceback
        traceback.print_exc()
        stripe_event.error_message = str(e)
        stripe_event.save()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def _send_subscription_activated_email(subscription):
    """Envia email de confirmação quando assinatura é ativada (checkout concluído)."""
    try:
        user = subscription.user
        if not user or not user.email:
            return
        nome = (user.first_name or '').strip() or (user.get_full_name() or user.username).strip() or 'Você'
        plano = f"{subscription.get_tier_display()} - {subscription.get_plan_display()}"
        site_url = getattr(settings, 'SITE_URL', 'https://www.educaflowone.com.br').rstrip('/')
        link_planos = f"{site_url}/planos/"
        link_login = f"{site_url}/login/"
        signature = getattr(settings, 'EMAIL_SIGNATURE', '')
        body = f"""Olá, {nome}! 🎉

Sua assinatura foi ativada com sucesso!

Plano: {plano}

Agora você tem acesso completo ao EDUCAflowOne. Comece a organizar seus alunos, aulas e pagamentos.

👉 Acessar minha conta
{link_login}

Para gerenciar sua assinatura (cartão, cancelamento, etc.):
{link_planos}

{signature}"""
        send_mail(
            subject='Assinatura ativada com sucesso ✅',
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        print(f"   Email de confirmação enviado para {user.email}")
    except Exception as e:
        print(f"   Erro ao enviar email de confirmação: {e}")


def _send_subscription_cancel_scheduled_email(subscription, period_end_date=None):
    """Envia email quando usuário agenda cancelamento (cancel_at_period_end)."""
    try:
        user = subscription.user
        if not user or not user.email:
            return
        nome = (user.first_name or '').strip() or (user.get_full_name() or user.username).strip() or 'Você'
        plano = f"{subscription.get_tier_display()} - {subscription.get_plan_display()}"
        site_url = getattr(settings, 'SITE_URL', 'https://www.educaflowone.com.br').rstrip('/')
        link_planos = f"{site_url}/planos/"
        signature = getattr(settings, 'EMAIL_SIGNATURE', '')
        data_fim = period_end_date or subscription.current_period_end
        data_str = data_fim.strftime('%d/%m/%Y') if data_fim else 'o fim do período atual'
        body = f"""Olá, {nome},

Recebemos sua solicitação de cancelamento da assinatura EDUCAflowOne.

Plano: {plano}
Cancelamento agendado para: {data_str}

Seu acesso ao sistema continua normalmente até essa data. Nenhuma nova cobrança será feita.

Mudou de ideia? Você pode desfazer o cancelamento a qualquer momento antes do fim do período:

👉 Gerenciar assinatura (desfazer cancelamento)
{link_planos}

Acesse a página de planos e clique em "Gerenciar assinatura" para reativar.

{signature}"""
        send_mail(
            subject='Cancelamento agendado – EDUCAflowOne',
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        print(f"   Email de cancelamento agendado enviado para {user.email}")
    except Exception as e:
        print(f"   Erro ao enviar email de cancelamento agendado: {e}")


def _send_subscription_canceled_email(subscription):
    """Envia email de confirmação quando assinatura é efetivamente cancelada (fim do período)."""
    try:
        user = subscription.user
        if not user or not user.email:
            return
        nome = (user.first_name or '').strip() or (user.get_full_name() or user.username).strip() or 'Você'
        plano = f"{subscription.get_tier_display()} - {subscription.get_plan_display()}"
        site_url = getattr(settings, 'SITE_URL', 'https://www.educaflowone.com.br').rstrip('/')
        link_planos = f"{site_url}/planos/"
        signature = getattr(settings, 'EMAIL_SIGNATURE', '')
        body = f"""Olá, {nome},

Recebemos a solicitação de cancelamento da sua assinatura EDUCAflowOne.

Plano cancelado: {plano}

Seu acesso ao sistema continuará até o fim do período já pago. Após isso, você precisará assinar novamente para voltar a usar.

Mudou de ideia? Você pode reativar a qualquer momento:

👉 Ver planos e assinar novamente
{link_planos}

Sentiremos sua falta! Se tiver feedback ou sugestões, é só responder este email.

{signature}"""
        send_mail(
            subject='Assinatura cancelada – EDUCAflowOne',
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        print(f"   Email de cancelamento enviado para {user.email}")
    except Exception as e:
        print(f"   Erro ao enviar email de cancelamento: {e}")


def _send_payment_failed_email(subscription):
    """Envia email quando pagamento falha (invoice.payment_failed)."""
    try:
        user = subscription.user
        if not user or not user.email:
            return
        nome = (user.first_name or '').strip() or (user.get_full_name() or user.username).strip() or 'Você'
        site_url = getattr(settings, 'SITE_URL', 'https://www.educaflowone.com.br').rstrip('/')
        link_planos = f"{site_url}/planos/"
        signature = getattr(settings, 'EMAIL_SIGNATURE', '')
        body = f"""Olá, {nome},

Não conseguimos processar o pagamento da sua assinatura EDUCAflowOne.

Possíveis causas:
• Cartão vencido ou limite estourado
• Dados do cartão incorretos
• Bloqueio pelo banco

Para continuar usando o sistema sem interrupções, atualize sua forma de pagamento:

👉 Atualizar forma de pagamento
{link_planos}

Acesse a página de planos e clique em "Gerenciar assinatura" para cadastrar um novo cartão.

O Stripe tentará cobrar novamente automaticamente. Se o problema persistir, sua assinatura poderá ser suspensa.

Precisa de ajuda? Responda este email ou entre em contato pelo WhatsApp.

{signature}"""
        send_mail(
            subject='⚠️ Problema no pagamento da sua assinatura',
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        print(f"   Email de pagamento falhou enviado para {user.email}")
    except Exception as e:
        print(f"   Erro ao enviar email de pagamento falhou: {e}")


def handle_checkout_session_completed(session):
    """Processa conclusão do checkout - ativa assinatura imediatamente"""
    print(f"🔍 handle_checkout_session_completed chamado")
    print(f"📋 Session data: subscription={session.get('subscription')}, customer={session.get('customer')}, client_reference_id={session.get('client_reference_id')}")
    
    subscription_id = session.get('subscription')
    customer_id = session.get('customer')
    client_reference_id = session.get('client_reference_id')  # user_id
    
    if not subscription_id:
        print("❌ Subscription ID não encontrado na session")
        return
    
    print(f"✅ Subscription ID encontrado: {subscription_id}")
    
    try:
        # Tentar encontrar subscription pelo subscription_id
        try:
            subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
            print(f"✅ Subscription encontrada no banco: {subscription.id}, status: {subscription.status}")
        except Subscription.DoesNotExist:
            print(f"⚠️ Subscription não encontrada no banco. Tentando criar...")
            # Se não encontrar, tentar criar a partir do customer_id ou client_reference_id
            user = None
            if client_reference_id:
                try:
                    user = User.objects.get(id=int(client_reference_id))
                except (User.DoesNotExist, ValueError):
                    pass
            
            if not user and customer_id:
                try:
                    stripe_customer = stripe.Customer.retrieve(customer_id)
                    user_id = stripe_customer.metadata.get('user_id')
                    if user_id:
                        user = User.objects.get(id=int(user_id))
                except Exception as e:
                    print(f"Erro ao obter user do customer: {e}")
            
            if not user:
                print(f"Não foi possível encontrar usuário para subscription {subscription_id}")
                return
            
            # Verificar se já existe subscription para este usuário
            try:
                existing_subscription = Subscription.objects.get(user=user)
                print(f"✅ Subscription existente encontrada para o usuário. Atualizando...")
                subscription = existing_subscription
                subscription.stripe_subscription_id = subscription_id
                subscription.stripe_customer_id = customer_id or subscription.stripe_customer_id
            except Subscription.DoesNotExist:
                # Obter dados da subscription do Stripe
                stripe_sub = stripe.Subscription.retrieve(subscription_id)
                price_id = stripe_sub['items']['data'][0]['price']['id']
                tier, plan = determine_plan_from_price_id(price_id)
                
                subscription = Subscription(
                    user=user,
                    tier=tier,
                    plan=plan,
                    status=Subscription.STATUS_ACTIVE,
                    stripe_customer_id=customer_id or stripe_sub.get('customer'),
                    stripe_subscription_id=subscription_id,
                )
            
            # Atualizar períodos da subscription do Stripe
            stripe_sub = stripe.Subscription.retrieve(subscription_id)
            # Usar getattr com valor padrão para evitar erro se o atributo não existir
            try:
                period_start = getattr(stripe_sub, 'current_period_start', None)
                if period_start:
                    subscription.current_period_start = timezone.make_aware(
                        datetime.fromtimestamp(period_start)
                    )
            except (AttributeError, KeyError, TypeError):
                pass
            
            try:
                period_end = getattr(stripe_sub, 'current_period_end', None)
                if period_end:
                    subscription.current_period_end = timezone.make_aware(
                        datetime.fromtimestamp(period_end)
                    )
            except (AttributeError, KeyError, TypeError):
                pass
            
            subscription.status = Subscription.STATUS_ACTIVE
            subscription.save()
            print(f"✅ Subscription salva/atualizada com sucesso!")
        
        # Ativar assinatura se ainda estiver pending
        if subscription.status == Subscription.STATUS_PENDING:
            print(f"🔄 Ativando assinatura (status atual: {subscription.status})...")
            subscription.status = Subscription.STATUS_ACTIVE
            
            # Atualizar período atual
            print(f"📅 Buscando dados da subscription no Stripe...")
            stripe_sub = stripe.Subscription.retrieve(subscription_id)
            # Usar getattr com valor padrão para evitar erro se o atributo não existir
            try:
                period_start = getattr(stripe_sub, 'current_period_start', None)
                if period_start:
                    subscription.current_period_start = timezone.make_aware(
                        datetime.fromtimestamp(period_start)
                    )
            except (AttributeError, KeyError, TypeError):
                pass
            
            try:
                period_end = getattr(stripe_sub, 'current_period_end', None)
                if period_end:
                    subscription.current_period_end = timezone.make_aware(
                        datetime.fromtimestamp(period_end)
                    )
            except (AttributeError, KeyError, TypeError):
                pass
            
            subscription.save()
            print(f"✅ Assinatura {subscription_id} ativada via checkout.session.completed")
            print(f"   Status: {subscription.status}")
            print(f"   Período: {subscription.current_period_start} até {subscription.current_period_end}")

        else:
            print(f"ℹ️ Assinatura já está com status: {subscription.status}")

        # Email de confirmação: checkout.session.completed = usuário acabou de concluir (trial ou pago)
        _send_subscription_activated_email(subscription)

    except Exception as e:
        print(f"Erro ao processar checkout.session.completed: {e}")
        import traceback
        traceback.print_exc()


def handle_subscription_created(subscription_obj):
    """Processa criação de assinatura - garante que está ativa"""
    subscription_id = subscription_obj.get('id')
    customer_id = subscription_obj.get('customer')
    
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        
        # Se estiver pending, ativar
        if subscription.status == Subscription.STATUS_PENDING:
            subscription.status = Subscription.STATUS_ACTIVE
            subscription.current_period_start = timezone.make_aware(
                datetime.fromtimestamp(subscription_obj.get('current_period_start', 0))
            )
            subscription.current_period_end = timezone.make_aware(
                datetime.fromtimestamp(subscription_obj.get('current_period_end', 0))
            )
            subscription.save()
            print(f"Assinatura {subscription_id} ativada via customer.subscription.created")
    except Subscription.DoesNotExist:
        # Tentar criar se não existir
        if customer_id:
            try:
                stripe_customer = stripe.Customer.retrieve(customer_id)
                user_id = stripe_customer.metadata.get('user_id')
                if user_id:
                    user = User.objects.get(id=int(user_id))
                    price_id = subscription_obj['items']['data'][0]['price']['id']
                    tier, plan = determine_plan_from_price_id(price_id)
                    
                    # Verificar se já existe subscription para este usuário
                    try:
                        subscription = Subscription.objects.get(user=user)
                        subscription.tier = tier
                        subscription.plan = plan
                        subscription.stripe_subscription_id = subscription_id
                        subscription.stripe_customer_id = customer_id
                    except Subscription.DoesNotExist:
                        subscription = Subscription(
                            user=user,
                            tier=tier,
                            plan=plan,
                            status=Subscription.STATUS_ACTIVE,
                            stripe_customer_id=customer_id,
                            stripe_subscription_id=subscription_id,
                        )
                    
                    subscription.current_period_start = timezone.make_aware(
                        datetime.fromtimestamp(subscription_obj.get('current_period_start', 0))
                    )
                    subscription.current_period_end = timezone.make_aware(
                        datetime.fromtimestamp(subscription_obj.get('current_period_end', 0))
                    )
                    subscription.status = Subscription.STATUS_ACTIVE
                    subscription.save()
            except Exception as e:
                print(f"Erro ao criar subscription: {e}")


def handle_invoice_paid(invoice):
    """Processa pagamento de invoice - ativa assinatura"""
    subscription_id = invoice.get('subscription')
    customer_id = invoice.get('customer')
    
    if not subscription_id:
        return
    
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        subscription.status = Subscription.STATUS_ACTIVE
        
        # Atualizar período atual
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        # Usar getattr com valor padrão para evitar erro se o atributo não existir
        try:
            period_start = getattr(stripe_sub, 'current_period_start', None)
            if period_start:
                subscription.current_period_start = timezone.make_aware(
                    datetime.fromtimestamp(period_start)
                )
        except (AttributeError, KeyError, TypeError):
            pass
        
        try:
            period_end = getattr(stripe_sub, 'current_period_end', None)
            if period_end:
                subscription.current_period_end = timezone.make_aware(
                    datetime.fromtimestamp(period_end)
                )
        except (AttributeError, KeyError, TypeError):
            pass
        
        subscription.save()
        
    except Subscription.DoesNotExist:
        # Tentar criar subscription a partir do customer_id
        if customer_id:
            try:
                stripe_customer = stripe.Customer.retrieve(customer_id)
                user_id = stripe_customer.metadata.get('user_id')
                if user_id:
                    user = User.objects.get(id=int(user_id))
                    stripe_sub = stripe.Subscription.retrieve(subscription_id)
                    
                    # Determinar plano a partir do price_id
                    price_id = stripe_sub['items']['data'][0]['price']['id']
                    tier, plan = determine_plan_from_price_id(price_id)
                    
                    # Verificar se já existe subscription para este usuário
                    try:
                        subscription = Subscription.objects.get(user=user)
                        subscription.tier = tier
                        subscription.plan = plan
                        subscription.stripe_subscription_id = subscription_id
                        subscription.stripe_customer_id = customer_id
                    except Subscription.DoesNotExist:
                        subscription = Subscription(
                            user=user,
                            tier=tier,
                            plan=plan,
                            status=Subscription.STATUS_ACTIVE,
                            stripe_customer_id=customer_id,
                            stripe_subscription_id=subscription_id,
                        )
                    
                    # Usar getattr com valor padrão para evitar erro se o atributo não existir
                    try:
                        period_start = getattr(stripe_sub, 'current_period_start', None)
                        if period_start:
                            subscription.current_period_start = timezone.make_aware(
                                datetime.fromtimestamp(period_start)
                            )
                    except (AttributeError, KeyError, TypeError):
                        pass
                    
                    try:
                        period_end = getattr(stripe_sub, 'current_period_end', None)
                        if period_end:
                            subscription.current_period_end = timezone.make_aware(
                                datetime.fromtimestamp(period_end)
                            )
                    except (AttributeError, KeyError, TypeError):
                        pass
                    
                    subscription.status = Subscription.STATUS_ACTIVE
                    subscription.save()
            except Exception as e:
                print(f"Erro ao criar subscription: {e}")


def handle_invoice_payment_failed(invoice):
    """Processa falha de pagamento - marca como past_due e envia email"""
    subscription_id = invoice.get('subscription')

    if not subscription_id:
        return

    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        subscription.status = Subscription.STATUS_PAST_DUE
        subscription.save()
        _send_payment_failed_email(subscription)
    except Subscription.DoesNotExist:
        pass


def handle_subscription_deleted(subscription_obj):
    """Processa cancelamento de assinatura e envia email de confirmação"""
    subscription_id = subscription_obj.get('id')
    
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        _send_subscription_canceled_email(subscription)
        subscription.status = Subscription.STATUS_CANCELED
        subscription.stripe_subscription_id = None  # Limpar referência
        subscription.save()
    except Subscription.DoesNotExist:
        pass


def handle_subscription_updated(subscription_obj):
    """Processa atualização de assinatura (ex.: troca de plano, cancelamento agendado)"""
    subscription_id = subscription_obj.get('id')
    cancel_at_period_end = subscription_obj.get('cancel_at_period_end', False)
    print(f"[subscription.updated] id={subscription_id} cancel_at_period_end={cancel_at_period_end}")
    
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
    except Subscription.DoesNotExist:
        print(f"[subscription.updated] Subscription nao encontrada: stripe_subscription_id={subscription_id}")
        return
    
    try:
        # Atualizar tier e plan a partir do novo price_id (quando usuário troca plano no portal)
        items = subscription_obj.get('items', {}).get('data', [])
        if items:
            price_id = items[0].get('price', {}).get('id')
            if price_id:
                tier, plan = determine_plan_from_price_id(price_id)
                subscription.tier = tier
                subscription.plan = plan
        
        # Atualizar período
        period_end_ts = subscription_obj.get('current_period_end', 0)
        subscription.current_period_start = timezone.make_aware(
            datetime.fromtimestamp(subscription_obj.get('current_period_start', 0))
        )
        subscription.current_period_end = timezone.make_aware(datetime.fromtimestamp(period_end_ts))
        
        # Atualizar status baseado no status do Stripe (trialing = trial 7 dias = acesso liberado)
        stripe_status = subscription_obj.get('status', '')
        if stripe_status in ('active', 'trialing'):
            subscription.status = Subscription.STATUS_ACTIVE
        elif stripe_status == 'past_due':
            subscription.status = Subscription.STATUS_PAST_DUE
        elif stripe_status == 'canceled' or stripe_status == 'unpaid':
            subscription.status = Subscription.STATUS_CANCELED
        
        # Se usuário desfez o cancelamento, limpar flag do email
        if not cancel_at_period_end:
            subscription.cancel_scheduled_email_sent_at = None
        
        subscription.cancel_at_period_end = cancel_at_period_end
        subscription.save()
        
        # Email quando usuário agenda cancelamento (envia 1 vez por agendamento)
        if cancel_at_period_end and not subscription.cancel_scheduled_email_sent_at:
            period_end_date = subscription.current_period_end
            _send_subscription_cancel_scheduled_email(subscription, period_end_date)
            subscription.cancel_scheduled_email_sent_at = timezone.now()
            subscription.save(update_fields=['cancel_scheduled_email_sent_at'])
            print(f"[subscription.updated] Email cancelamento agendado enviado para {subscription.user.email}")
        
    except Exception as e:
        print(f"[subscription.updated] Erro: {e}")
        import traceback
        traceback.print_exc()


def determine_plan_from_price_id(price_id):
    """Determina o tier e periodicidade a partir do price_id do Stripe"""
    # Mapeamento completo de price_ids para (tier, plan)
    price_mapping = {
        os.environ.get("STRIPE_PRICE_ID_BASIC_MONTHLY", ""): (Subscription.TIER_BASIC, Subscription.PLAN_MONTHLY),
        os.environ.get("STRIPE_PRICE_ID_BASIC_SEMESTRAL", ""): (Subscription.TIER_BASIC, Subscription.PLAN_SEMESTRAL),
        os.environ.get("STRIPE_PRICE_ID_BASIC_ANNUAL", ""): (Subscription.TIER_BASIC, Subscription.PLAN_ANNUAL),
        os.environ.get("STRIPE_PRICE_ID_PREMIUM_MONTHLY", ""): (Subscription.TIER_PREMIUM, Subscription.PLAN_MONTHLY),
        os.environ.get("STRIPE_PRICE_ID_PREMIUM_SEMESTRAL", ""): (Subscription.TIER_PREMIUM, Subscription.PLAN_SEMESTRAL),
        os.environ.get("STRIPE_PRICE_ID_PREMIUM_ANNUAL", ""): (Subscription.TIER_PREMIUM, Subscription.PLAN_ANNUAL),
        os.environ.get("STRIPE_PRICE_ID_PLATINUM_MONTHLY", ""): (Subscription.TIER_PLATINUM, Subscription.PLAN_MONTHLY),
        os.environ.get("STRIPE_PRICE_ID_PLATINUM_SEMESTRAL", ""): (Subscription.TIER_PLATINUM, Subscription.PLAN_SEMESTRAL),
        os.environ.get("STRIPE_PRICE_ID_PLATINUM_ANNUAL", ""): (Subscription.TIER_PLATINUM, Subscription.PLAN_ANNUAL),
    }
    
    result = price_mapping.get(price_id)
    if result:
        return result  # Retorna (tier, plan)
    
    # Fallback para compatibilidade com planos antigos (se houver)
    monthly_id = os.environ.get("STRIPE_PRICE_ID_MONTHLY", "")
    semestral_id = os.environ.get("STRIPE_PRICE_ID_SEMESTRAL", "")
    annual_id = os.environ.get("STRIPE_PRICE_ID_ANNUAL", "")
    
    if price_id == monthly_id:
        return (Subscription.TIER_BASIC, Subscription.PLAN_MONTHLY)  # Default para basic
    elif price_id == semestral_id:
        return (Subscription.TIER_BASIC, Subscription.PLAN_SEMESTRAL)
    elif price_id == annual_id:
        return (Subscription.TIER_BASIC, Subscription.PLAN_ANNUAL)
    
    # Default
    return (Subscription.TIER_BASIC, Subscription.PLAN_MONTHLY)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_checkout_session(request):
    """
    Verifica e processa uma checkout session do Stripe diretamente.
    Útil quando o webhook não chegou a tempo.
    Body: {session_id: "cs_test_..."}
    """
    session_id = request.data.get('session_id')
    if not session_id:
        return Response(
            {'error': 'session_id é obrigatório'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Buscar a session do Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        # Sessão deve estar completa
        if checkout_session.status != 'complete':
            return Response(
                {'error': f'Sessão de checkout ainda não foi concluída (status: {checkout_session.status})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        subscription_id = checkout_session.subscription
        
        if not subscription_id:
            return Response(
                {'error': 'Nenhuma subscription encontrada nesta sessão'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar ou atualizar subscription localmente
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        # Trial = status "trialing"; ativar imediatamente para dar acesso
        stripe_status = stripe_sub.get('status', '')
        price_id = stripe_sub['items']['data'][0]['price']['id']
        tier, plan = determine_plan_from_price_id(price_id)
        
        try:
            subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        except Subscription.DoesNotExist:
            # Pode ser a subscription criada no início do checkout (sem stripe_subscription_id ainda)
            try:
                subscription = Subscription.objects.get(user=request.user)
                # Atualizar com dados do Stripe e ativar
                subscription.stripe_subscription_id = subscription_id
                subscription.stripe_customer_id = subscription.stripe_customer_id or checkout_session.customer
                subscription.tier = tier
                subscription.plan = plan
                subscription.status = Subscription.STATUS_ACTIVE
            except Subscription.DoesNotExist:
                # Criar nova subscription
                subscription = Subscription.objects.create(
                    user=request.user,
                    tier=tier,
                    plan=plan,
                    status=Subscription.STATUS_ACTIVE,
                    stripe_customer_id=checkout_session.customer,
                    stripe_subscription_id=subscription_id,
                )
        
        # Trialing ou active no Stripe = ativo aqui (acesso liberado no trial)
        if stripe_status in ('active', 'trialing'):
            subscription.status = Subscription.STATUS_ACTIVE
        subscription.stripe_subscription_id = subscription_id
        subscription.tier = tier
        subscription.plan = plan
        subscription.stripe_customer_id = subscription.stripe_customer_id or checkout_session.customer
        try:
            period_start = stripe_sub.get('current_period_start')
            period_end = stripe_sub.get('current_period_end')
            if period_start:
                subscription.current_period_start = timezone.make_aware(
                    datetime.fromtimestamp(period_start)
                )
            if period_end:
                subscription.current_period_end = timezone.make_aware(
                    datetime.fromtimestamp(period_end)
                )
        except Exception as e:
            print(f"Erro ao atualizar períodos: {e}")
        subscription.save()

        amount_total = getattr(checkout_session, 'amount_total', None) or checkout_session.get('amount_total')
        
        return Response({
            'success': True,
            'has_subscription': True,
            'tier': subscription.tier,
            'plan': subscription.plan,
            'status': subscription.status,
            'is_active': subscription.is_active,
            'amount_total': amount_total,
        })
        
    except stripe.error.StripeError as e:
        return Response(
            {'error': f'Erro ao verificar sessão no Stripe: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {'error': f'Erro inesperado: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_status(request):
    """Retorna o status da assinatura do usuário"""
    try:
        subscription = request.user.subscription
        return Response({
            'has_subscription': True,
            'tier': subscription.tier,
            'plan': subscription.plan,
            'status': subscription.status,
            'is_active': subscription.is_active,
            'current_period_end': subscription.current_period_end,
        })
    except Subscription.DoesNotExist:
        return Response({
            'has_subscription': False,
            'plan': None,
            'status': None,
            'is_active': False,
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscription_sync(request):
    """
    Força sincronização da assinatura com o Stripe.
    Útil quando o Stripe mostra ativo/trialing mas o sistema exibe Pendente.
    Admin pode passar user_id no body para sincronizar outro usuário.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user_id = request.data.get('user_id')
    try:
        if user_id is not None:
            is_admin = getattr(request.user.profile, 'is_admin', False)
            if not is_admin:
                return Response({'error': 'Apenas administradores podem sincronizar outros usuários'}, status=status.HTTP_403_FORBIDDEN)
            target_user = User.objects.get(pk=user_id)
            subscription = target_user.subscription
        else:
            subscription = request.user.subscription
        _sync_subscription_from_stripe(subscription, raise_on_error=True)
        subscription.refresh_from_db()
        return Response({
            'ok': True,
            'status': subscription.status,
            'is_active': subscription.is_active,
        })
    except User.DoesNotExist:
        return Response({'error': 'Usuário não encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Subscription.DoesNotExist:
        return Response({'error': 'Assinatura não encontrada'}, status=status.HTTP_404_NOT_FOUND)
    except (ValueError, stripe.error.StripeError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_portal_session(request):
    """
    Cria uma sessão do Stripe Customer Portal para o usuário gerenciar sua assinatura.
    Retorna a URL do portal para redirecionamento.
    """
    try:
        subscription = request.user.subscription
        
        if not subscription.stripe_customer_id:
            return Response(
                {'error': 'Cliente não encontrado no Stripe'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # URLs de retorno
        base_url = request.build_absolute_uri('/')[:-1]
        return_url = f"{base_url}/planos/"
        
        # Criar sessão do Customer Portal
        portal_session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=return_url,
        )
        
        return Response({
            'url': portal_session.url
        })
        
    except Subscription.DoesNotExist:
        return Response(
            {'error': 'Assinatura não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except stripe.error.StripeError as e:
        return Response(
            {'error': f'Erro ao criar sessão do portal: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {'error': f'Erro inesperado: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upgrade_portal_session(request):
    """
    Cria sessão do portal Stripe para upgrade de plano (ex.: Basic → Premium).
    Body: { tier: 'premium'|'platinum', plan: 'monthly'|'semestral'|annual' }
    Redireciona o cliente direto para a tela de confirmação do novo preço.
    """
    tier = request.data.get('tier', '').strip().lower()
    plan = request.data.get('plan', 'monthly').strip().lower()
    if tier not in [Subscription.TIER_PREMIUM, Subscription.TIER_PLATINUM]:
        return Response({'error': 'Para upgrade, escolha Premium ou Platinum'}, status=status.HTTP_400_BAD_REQUEST)
    if plan not in [Subscription.PLAN_MONTHLY, Subscription.PLAN_SEMESTRAL, Subscription.PLAN_ANNUAL]:
        return Response({'error': 'Periodicidade inválida'}, status=status.HTTP_400_BAD_REQUEST)
    plan_key = f"{tier}_{plan}"
    PLAN_PRICE_IDS = {
        f"{Subscription.TIER_PREMIUM}_{Subscription.PLAN_MONTHLY}": os.environ.get("STRIPE_PRICE_ID_PREMIUM_MONTHLY", ""),
        f"{Subscription.TIER_PREMIUM}_{Subscription.PLAN_SEMESTRAL}": os.environ.get("STRIPE_PRICE_ID_PREMIUM_SEMESTRAL", ""),
        f"{Subscription.TIER_PREMIUM}_{Subscription.PLAN_ANNUAL}": os.environ.get("STRIPE_PRICE_ID_PREMIUM_ANNUAL", ""),
        f"{Subscription.TIER_PLATINUM}_{Subscription.PLAN_MONTHLY}": os.environ.get("STRIPE_PRICE_ID_PLATINUM_MONTHLY", ""),
        f"{Subscription.TIER_PLATINUM}_{Subscription.PLAN_SEMESTRAL}": os.environ.get("STRIPE_PRICE_ID_PLATINUM_SEMESTRAL", ""),
        f"{Subscription.TIER_PLATINUM}_{Subscription.PLAN_ANNUAL}": os.environ.get("STRIPE_PRICE_ID_PLATINUM_ANNUAL", ""),
    }
    price_id = PLAN_PRICE_IDS.get(plan_key)
    if not price_id:
        return Response({'error': f'Preço não configurado para {tier} {plan}. Configure STRIPE_PRICE_ID_{tier.upper()}_{plan.upper()}.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    try:
        subscription = request.user.subscription
        if not subscription.stripe_subscription_id:
            return Response({'error': 'Assinatura não encontrada no Stripe'}, status=status.HTTP_404_NOT_FOUND)
        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
        items = stripe_sub.get('items', {}).get('data', [])
        if not items:
            return Response({'error': 'Assinatura sem itens no Stripe'}, status=status.HTTP_400_BAD_REQUEST)
        sub_item_id = items[0]['id']
        base_url = request.build_absolute_uri('/')[:-1]
        return_url = f"{base_url}/planos/"
        portal_session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=return_url,
            flow_data={
                'type': 'subscription_update_confirm',
                'subscription_update_confirm': {
                    'subscription': subscription.stripe_subscription_id,
                    'items': [{'id': sub_item_id, 'price': price_id, 'quantity': 1}],
                },
                'after_completion': {
                    'type': 'redirect',
                    'redirect': {'return_url': return_url},
                },
            },
        )
        return Response({'url': portal_session.url})
    except Subscription.DoesNotExist:
        return Response({'error': 'Assinatura não encontrada'}, status=status.HTTP_404_NOT_FOUND)
    except stripe.error.StripeError as e:
        err_msg = str(e)
        if 'configuration' in err_msg.lower() or 'product' in err_msg.lower():
            return Response({
                'error': 'O preço de destino não está configurado no portal do Stripe. Em Stripe Dashboard → Settings → Billing → Customer portal, ative "Switch plan" e inclua os produtos Premium e Platinum.'
            }, status=status.HTTP_400_BAD_REQUEST)
        return Response({'error': err_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _sync_subscription_from_stripe(subscription, raise_on_error=False):
    """
    Atualiza tier/plan/período da Subscription com dados do Stripe.
    Útil ao retornar do portal Stripe (webhook pode demorar).
    Se tiver stripe_customer_id mas não stripe_subscription_id, tenta recuperar do Stripe.
    Se raise_on_error=True, propaga exceções (útil para endpoints que precisam retornar erro).
    """
    if not subscription:
        return
    try:
        # Fallback: se não tem stripe_subscription_id mas tem customer_id, buscar subscriptions do cliente
        if not subscription.stripe_subscription_id and subscription.stripe_customer_id:
            subs = stripe.Subscription.list(customer=subscription.stripe_customer_id, status='all', limit=5)
            for s in subs.data:
                if s.get('status') in ('active', 'trialing'):
                    subscription.stripe_subscription_id = s.get('id')
                    subscription.save()
                    break
        if not subscription.stripe_subscription_id:
            if raise_on_error:
                raise ValueError('Nenhuma assinatura ativa encontrada no Stripe para este cliente.')
            return
        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
        items = stripe_sub.get('items', {}).get('data', [])
        if items:
            price_id = items[0].get('price', {}).get('id')
            if price_id:
                tier, plan = determine_plan_from_price_id(price_id)
                subscription.tier = tier
                subscription.plan = plan
        period_start = stripe_sub.get('current_period_start')
        period_end = stripe_sub.get('current_period_end')
        if period_start:
            subscription.current_period_start = timezone.make_aware(datetime.fromtimestamp(period_start))
        if period_end:
            subscription.current_period_end = timezone.make_aware(datetime.fromtimestamp(period_end))
        stripe_status = stripe_sub.get('status', '')
        if stripe_status in ('active', 'trialing'):
            subscription.status = Subscription.STATUS_ACTIVE
        elif stripe_status == 'past_due':
            subscription.status = Subscription.STATUS_PAST_DUE
        elif stripe_status in ('canceled', 'unpaid'):
            subscription.status = Subscription.STATUS_CANCELED
        subscription.cancel_at_period_end = stripe_sub.get('cancel_at_period_end', False)
        subscription.save()
    except Exception:
        if raise_on_error:
            raise
        pass  # Mantém dados locais em caso de erro


class PlanosView(TemplateView):
    """View para exibir página de planos e faturamento"""
    template_name = 'planos.html'
    login_required = True
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        try:
            profile = user.profile
            context['user_is_admin'] = profile.is_admin
            context['is_partner_teacher'] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
        except UserProfile.DoesNotExist:
            context['user_is_admin'] = False
            context['is_partner_teacher'] = False
        
        # Obter dados da assinatura
        try:
            subscription = user.subscription
            # Sincronizar com Stripe ao carregar (garante que alterações no portal apareçam)
            # ?skip_sync=1 pula o sync para testar o botão "Atualizar status" com status pendente forçado
            if not self.request.GET.get('skip_sync'):
                _sync_subscription_from_stripe(subscription)
            subscription.refresh_from_db()
            context['subscription'] = subscription
            context['has_subscription'] = True
            context['is_active'] = subscription.is_active
            
            # Formatar nome do plano (tier + periodicidade)
            tier_names = {
                'basic': 'Basic',
                'premium': 'Premium',
                'platinum': 'Platinum'
            }
            plan_names = {
                'monthly': 'Mensal',
                'semestral': 'Semestral',
                'annual': 'Anual'
            }
            tier_display = tier_names.get(subscription.tier, subscription.get_tier_display())
            plan_display = plan_names.get(subscription.plan, subscription.get_plan_display())
            context['plan_name'] = f'{tier_display} - {plan_display}'
            context['tier'] = subscription.tier
            
            # Formatar preço (buscar do Stripe se necessário)
            plan_prices = {
                ('basic', 'monthly'): 'R$ 49,90',
                ('basic', 'semestral'): 'R$ 269,40',
                ('basic', 'annual'): 'R$ 479,00',
                ('premium', 'monthly'): 'R$ 69,90',
                ('premium', 'semestral'): 'R$ 377,40',
                ('premium', 'annual'): 'R$ 699,00',
                ('platinum', 'monthly'): 'R$ 89,90',
                ('platinum', 'semestral'): 'R$ 485,40',
                ('platinum', 'annual'): 'R$ 899,00',
            }
            context['plan_price'] = plan_prices.get((subscription.tier, subscription.plan), '—')
            
            # Formatar período
            if subscription.current_period_end:
                context['next_billing'] = subscription.current_period_end.strftime('%d/%m/%Y')
            else:
                context['next_billing'] = '—'
                
        except Subscription.DoesNotExist:
            context['subscription'] = None
            context['has_subscription'] = False
            context['is_active'] = False
            context['plan_name'] = 'Nenhum plano ativo'
            context['plan_price'] = '—'
            context['next_billing'] = '—'

        # Contadores para aviso ao assinar (trial com muitos dados → Basic não cabe)
        # Conta apenas alunos ATIVOS (pausados/encerrados não entram no limite)
        context['student_count'] = Student.objects.filter(user=user, status=Student.STATUS_ACTIVE).count()
        try:
            context['partner_count'] = user.profile.partner_teachers.count()
        except UserProfile.DoesNotExist:
            context['partner_count'] = 0
        context['basic_plan_unavailable'] = context['student_count'] > 15
        context['premium_plan_unavailable'] = context['partner_count'] > 2

        # Buscar histórico de invoices do Stripe
        invoices = []
        if context.get('has_subscription'):
            try:
                subscription_obj = user.subscription
                if subscription_obj and subscription_obj.stripe_customer_id:
                    stripe_invoices = stripe.Invoice.list(
                        customer=subscription_obj.stripe_customer_id,
                        limit=20,
                        expand=['data.charge']
                    )
                    
                    for inv in stripe_invoices.data:
                        # Formatar data
                        timestamp = getattr(inv, 'created', None) or 0
                        if timestamp:
                            from datetime import datetime
                            date_str = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y')
                        else:
                            date_str = '—'
                        
                        # Descrição
                        description = 'Assinatura'
                        inv_lines = getattr(inv, 'lines', None)
                        if inv_lines and hasattr(inv_lines, 'data') and inv_lines.data:
                            line = inv_lines.data[0]
                            if hasattr(line, 'description') and line.description:
                                description = line.description
                            elif hasattr(line, 'plan') and line.plan:
                                plan_name = getattr(line.plan, 'nickname', None) or getattr(line.plan, 'id', '')
                                if plan_name:
                                    description = f'Plano {plan_name}'
                        
                        # Status
                        status = 'pending'
                        status_label = 'Processando'
                        inv_status = getattr(inv, 'status', None)
                        inv_paid = getattr(inv, 'paid', False)
                        
                        if inv_paid:
                            status = 'paid'
                            status_label = 'Pago'
                        elif inv_status == 'open':
                            status = 'pending'
                            status_label = 'Pendente'
                        elif inv_status == 'void':
                            status = 'failed'
                            status_label = 'Cancelado'
                        elif inv_status == 'uncollectible':
                            status = 'failed'
                            status_label = 'Falhou'
                        elif inv_status == 'draft':
                            status = 'pending'
                            status_label = 'Rascunho'
                        elif inv_status == 'paid':
                            status = 'paid'
                            status_label = 'Pago'
                        
                        # Valor
                        amount_str = '—'
                        amount_paid = getattr(inv, 'amount_paid', None)
                        amount_due = getattr(inv, 'amount_due', None)
                        total = getattr(inv, 'total', None)
                        
                        if amount_paid:
                            amount = amount_paid / 100  # Stripe usa centavos
                            amount_str = f'R$ {amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
                        elif amount_due:
                            amount = amount_due / 100
                            amount_str = f'R$ {amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
                        elif total:
                            amount = total / 100
                            amount_str = f'R$ {amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
                        
                        # Link do recibo
                        receipt_url = getattr(inv, 'hosted_invoice_url', None) or getattr(inv, 'invoice_pdf', None) or '#'
                        
                        invoices.append({
                            'date': date_str,
                            'description': description,
                            'status': status,
                            'status_label': status_label,
                            'amount': amount_str,
                            'receipt_url': receipt_url,
                            'timestamp': timestamp,  # Para ordenação
                        })
                    
                    # Ordenar por timestamp (mais recente primeiro)
                    invoices.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
                    # Remover timestamp antes de passar para o template
                    for inv in invoices:
                        inv.pop('timestamp', None)
                    
            except Exception as e:
                print(f"Erro ao buscar invoices do Stripe: {e}")
                import traceback
                traceback.print_exc()
                invoices = []
        
        context['invoices'] = invoices
        
        return context


def _send_internal_signup_notification(request, user):
    """
    E-mail interno quando um novo usuário se cadastra (trial).
    Usa o mesmo backend configurado em settings (Resend via Anymail quando RESEND_API_KEY).
    """
    if not getattr(settings, "INTERNAL_SIGNUP_NOTIFY_ENABLED", True):
        return
    to_addr = (getattr(settings, "INTERNAL_SIGNUP_NOTIFY_TO", "") or "").strip()
    if not to_addr:
        return
    cc_raw = getattr(settings, "INTERNAL_SIGNUP_NOTIFY_CC", "") or ""
    cc_list = [
        x.strip()
        for x in re.split(r"[,;]", cc_raw)
        if x and x.strip()
    ]
    trial_end = None
    try:
        trial_end = user.profile.trial_ends_at
    except Exception:
        pass
    trial_str = trial_end.isoformat() if trial_end else "-"
    subject = f"[EducaflowOne] Novo cadastro: {user.username}"
    body = f"""Novo usuário registrado (trial).

ID: {user.id}
Username: {user.username}
E-mail: {user.email}
Nome: {(user.first_name or '').strip()} {(user.last_name or '').strip()}
Trial até: {trial_str}

Login: {getattr(settings, 'SITE_URL', 'https://www.educaflowone.com.br').rstrip('/')}/login/
"""
    try:
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_addr],
            cc=cc_list,
        )
        msg.send(fail_silently=True)
    except Exception as e:
        print(f"[Signup] Erro ao enviar notificação interna de cadastro: {e}")


def _send_signup_welcome_and_hooks(request, user):
    """E-mail de boas-vindas, notificação interna e webhook n8n (mesmo fluxo do signup manual)."""
    email = user.email
    nome = (
        (user.first_name or '').strip()
        or (user.get_full_name() or user.username).strip()
        or 'Você'
    )
    link_login = f"{getattr(settings, 'SITE_URL', 'https://www.educaflowone.com.br').rstrip('/')}/login/"
    welcome_body = f"""Olá, {nome}! 👋

Que bom ter você no EducaflowOne 😊

Você tem 7 dias grátis para experimentar - sem cadastrar cartão. Use à vontade e decida depois.

Para começar rápido:

1️⃣ Cadastre seu primeiro aluno
2️⃣ Adicione uma aula na agenda
3️⃣ Veja sua agenda organizada

No 5º dia avisaremos que o trial está terminando. No 7º dia, para continuar, basta escolher um plano na tela de planos.

👉 Acessar minha conta agora
{link_login}

Aproveite! Se tiver dúvidas, responda este e-mail.

"""
    _sig_raw = getattr(settings, 'EMAIL_SIGNATURE', '')
    _sig_welcome = '\n'.join(
        ln for ln in _sig_raw.splitlines() if 'whatsapp' not in ln.lower()
    ).strip()
    if _sig_welcome:
        welcome_body = welcome_body + _sig_welcome + '\n'
    try:
        send_mail(
            subject='Bem-vindo ao Educaflow 🎉',
            message=welcome_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"[Signup] Erro ao enviar email de boas-vindas: {e}")

    try:
        _send_internal_signup_notification(request, user)
    except Exception as e:
        print(f"[Signup] Erro ao notificar cadastro interno: {e}")

    try:
        _trigger_n8n_onboarding_webhook(request, user)
    except Exception as e:
        print(f"[Signup] Erro ao disparar webhook onboarding n8n: {e}")


def _google_suggested_username(email: str, sub: str) -> str:
    """Username único a partir do e-mail Google + sufixo estável."""
    local = (email.split('@')[0] if '@' in email else 'user').lower()
    base = re.sub(r'[^a-z0-9_]', '_', local)
    base = re.sub(r'_+', '_', base).strip('_')[:80] or 'user'
    digits = re.sub(r'\D', '', sub or '')
    tail = (digits[-8:] if len(digits) >= 4 else None) or (sub.replace('-', '')[-8:] if sub else '') or 'google'
    candidate = base
    if User.objects.filter(username__iexact=candidate).exists():
        candidate = f'{base}_{tail}'[:150]
    n = 0
    while User.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f'{base}_{tail}_{n}'[:150]
    return candidate


def _sync_user_from_google_idtoken(user, idinfo: dict) -> None:
    """
    Persiste no User/UserProfile o que o JWT do Sign in with Google expõe.

    Inclui tipicamente: sub, email (já aplicado), email_verified, name, given_name,
    family_name, picture, locale; em contas Workspace também hd (domínio).

    Não inclui telefone: o id_token do fluxo padrão GIS não traz phone_number;
    seria necessário OAuth com escopos extras + People API.
    """
    given = (idinfo.get('given_name') or '')[:150]
    family = (idinfo.get('family_name') or '')[:150]
    full_name = (idinfo.get('name') or '').strip()

    u_fields = []
    if given and not (user.first_name or '').strip():
        user.first_name = given
        u_fields.append('first_name')
    if family and not (user.last_name or '').strip():
        user.last_name = family
        u_fields.append('last_name')
    if not u_fields and full_name and not (user.first_name or '').strip():
        parts = full_name.split(None, 1)
        user.first_name = (parts[0] or '')[:150]
        user.last_name = (parts[1] if len(parts) > 1 else '')[:150]
        u_fields.extend(['first_name', 'last_name'])
    if u_fields:
        user.save(update_fields=list(dict.fromkeys(u_fields)))

    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'user_profile': UserProfile.PROFILE_TEACHER,
            'is_admin': False,
            'trial_ends_at': timezone.now() + timedelta(days=7),
        },
    )
    p_fields = []
    sub = (idinfo.get('sub') or '').strip()[:255]
    if sub and profile.google_sub != sub:
        if not UserProfile.objects.filter(google_sub=sub).exclude(pk=profile.pk).exists():
            profile.google_sub = sub
            p_fields.append('google_sub')
        else:
            print(f"[Google auth] google_sub já vinculado a outro perfil; user_id={user.id}")
    pic = (idinfo.get('picture') or '').strip()
    if pic:
        pic = pic[:2048]
        if profile.google_picture_url != pic:
            profile.google_picture_url = pic
            p_fields.append('google_picture_url')
    locale = (idinfo.get('locale') or '').strip()
    if locale:
        lang = locale.replace('_', '-')[:10]
        if profile.language != lang:
            profile.language = lang
            p_fields.append('language')
    hd = (idinfo.get('hd') or '').strip()[:255]
    if hd and profile.google_hosted_domain != hd:
        profile.google_hosted_domain = hd
        p_fields.append('google_hosted_domain')
    if p_fields:
        p_fields.append('updated_at')
        try:
            profile.save(update_fields=list(dict.fromkeys(p_fields)))
        except IntegrityError:
            print(f"[Google auth] IntegrityError ao salvar perfil Google user_id={user.id}")


def _session_login_payload(user):
    """Mesmo shape que login_view (sem chamar login())."""
    try:
        is_admin = user.profile.is_admin
        user_profile = user.profile.user_profile
    except UserProfile.DoesNotExist:
        is_admin = False
        user_profile = None
    return {
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_admin': is_admin,
            'user_profile': user_profile,
        },
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def signup_view(request):
    """
    Endpoint público para criar conta de usuário.
    Usado no fluxo de signup antes do pagamento.
    """
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')
    password_confirm = request.data.get('password_confirm')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')
    
    if not username or not email or not password:
        return Response(
            {'error': 'Username, email e senha são obrigatórios'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validar confirmação de senha
    if not password_confirm:
        return Response(
            {'error': 'Confirmação de senha é obrigatória'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if password != password_confirm:
        return Response(
            {'error': 'As senhas não coincidem'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verificar se usuário já existe
    if User.objects.filter(username=username).exists():
        return Response(
            {'error': 'Este nome de usuário já está em uso'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if User.objects.filter(email=email).exists():
        return Response(
            {'error': 'Este e-mail já está em uso'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Criar usuário
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        
        # Criar perfil com trial gratuito de 7 dias (sem cartão)
        UserProfile.objects.create(
            user=user,
            user_profile=UserProfile.PROFILE_TEACHER,
            is_admin=False,
            trial_ends_at=timezone.now() + timedelta(days=7),
        )

        _send_signup_welcome_and_hooks(request, user)

        return Response({
            'success': True,
            'user_id': user.id,
            'username': user.username,
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao criar usuário: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _google_auth_run(request, credential: str) -> dict:
    """
    Núcleo do login/cadastro Google. credential = JWT (id_token).
    Retorno:
      {'ok': True, 'user': User, 'created': bool}
      {'ok': False, 'status': int, 'error': str, 'err_code': str}
    err_code: 'config', 'nocred', 'invalid', 'noemail', 'unverified', 'server'
    """
    client_id = (getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '') or '').strip()
    if client_id.startswith('"') and client_id.endswith('"'):
        client_id = client_id[1:-1].strip()
    if not client_id:
        return {'ok': False, 'status': 501, 'error': 'Login com Google não configurado.', 'err_code': 'config'}

    credential = (credential or '').strip()
    if not credential:
        return {'ok': False, 'status': 400, 'error': 'Token do Google ausente.', 'err_code': 'nocred'}

    def _jwt_aud_debug():
        """Só diagnóstico: aud do JWT vs Client ID no Django (sem validar assinatura)."""
        try:
            parts = credential.split('.')
            if len(parts) < 2:
                return
            pad = '=' * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
            aud = payload.get('aud')
            match = aud == client_id or (isinstance(aud, list) and client_id in aud)
            print(
                f"[Google auth] JWT aud={aud!r} client_id={client_id!r} audience_match={match} "
                f"iss={payload.get('iss')!r}"
            )
        except Exception as ex:
            print(f"[Google auth] JWT debug decode: {ex}")

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_auth_requests

        idinfo = google_id_token.verify_oauth2_token(
            credential,
            google_auth_requests.Request(),
            client_id,
            clock_skew_in_seconds=120,
        )
    except ValueError as e:
        _jwt_aud_debug()
        print(f"[Google auth] verify_oauth2_token ValueError: {e!r}")
        err_txt = 'Token Google inválido ou expirado. Tente de novo.'
        if getattr(settings, 'DEBUG', False):
            err_txt = f'Token Google recusado na verificação: {e}'
        return {'ok': False, 'status': 401, 'error': err_txt, 'err_code': 'invalid'}
    except Exception as e:
        _jwt_aud_debug()
        print(f"[Google auth] verify_oauth2_token {type(e).__name__}: {e!r}")
        return {'ok': False, 'status': 502, 'error': f'Erro ao validar Google: {e}', 'err_code': 'invalid'}

    email = (idinfo.get('email') or '').strip().lower()
    if not email:
        return {'ok': False, 'status': 400, 'error': 'Conta Google sem e-mail.', 'err_code': 'noemail'}
    if not idinfo.get('email_verified'):
        return {
            'ok': False,
            'status': 400,
            'error': 'Confirme o e-mail na sua conta Google antes de continuar.',
            'err_code': 'unverified',
        }

    given = (idinfo.get('given_name') or '')[:150]
    family = (idinfo.get('family_name') or '')[:150]
    sub = idinfo.get('sub') or ''

    existing = User.objects.filter(email__iexact=email).first()
    if existing:
        _sync_user_from_google_idtoken(existing, idinfo)
        login(request, existing)
        request.session.save()
        return {'ok': True, 'user': existing, 'created': False}

    username = _google_suggested_username(email, sub)
    try:
        user = User(
            username=username,
            email=email,
            first_name=given,
            last_name=family,
        )
        user.set_unusable_password()
        user.save()
        UserProfile.objects.create(
            user=user,
            user_profile=UserProfile.PROFILE_TEACHER,
            is_admin=False,
            trial_ends_at=timezone.now() + timedelta(days=7),
        )
    except Exception as e:
        return {'ok': False, 'status': 500, 'error': f'Erro ao criar conta: {str(e)}', 'err_code': 'server'}

    _sync_user_from_google_idtoken(user, idinfo)

    _send_signup_welcome_and_hooks(request, user)
    login(request, user)
    request.session.save()
    return {'ok': True, 'user': user, 'created': True}


@api_view(['POST'])
@permission_classes([AllowAny])
def google_auth_view(request):
    """
    Cadastro/login com Google (JWT) — chamada AJAX (legado / fallback).
    Body: { "credential": "<id_token>" }
    """
    credential = (request.data.get('credential') or request.data.get('id_token') or '').strip()
    result = _google_auth_run(request, credential)
    if not result['ok']:
        return Response({'error': result['error']}, status=result['status'])
    user = result['user']
    payload = _session_login_payload(user)
    payload['created'] = result['created']
    st = status.HTTP_201_CREATED if result['created'] else status.HTTP_200_OK
    return Response(payload, status=st)


def _google_oauth_err_messages() -> dict:
    return {
        'csrf': 'Falha na verificação com Google. Tente novamente.',
        'invalid': 'Login com Google inválido ou expirado. Tente de novo.',
        'nocred': 'Dados do Google incompletos. Tente novamente.',
        'invalid_flow': 'Acesso inválido ao retorno do Google.',
        'unverified': 'Confirme o e-mail na sua conta Google antes de continuar.',
        'noemail': 'Conta Google sem e-mail.',
        'config': 'Login com Google não está configurado.',
        'server': 'Erro ao criar conta. Tente mais tarde.',
        'error': 'Não foi possível entrar com Google.',
    }


def _google_oauth_page_context(request) -> dict:
    err = request.GET.get('google_err', '').strip()
    msgs = _google_oauth_err_messages()
    return {
        'google_oauth_client_id': getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '') or '',
        'google_login_uri': request.build_absolute_uri(reverse('api-google-callback')),
        'google_oauth_error_text': msgs.get(err, '') if err else '',
    }


def _google_oauth_source_return(request) -> str:
    """Cookie go_from=login|signup (set no front) — evita ?from= na URI do callback."""
    src = (request.COOKIES.get('go_from') or 'signup').strip().lower()
    return reverse('login') if src == 'login' else reverse('signup')


@csrf_exempt
def google_auth_redirect_view(request):
    """
    GIS ux_mode=redirect: o Google faz POST (form) nesta URL com credential (+ g_csrf_token).
    Sem popup — evita tela branca em gsi/transform no Chrome/anônimo.
    """
    ret = _google_oauth_source_return(request)
    if request.method == 'GET':
        return HttpResponseRedirect(f'{ret}?google_err=invalid_flow')

    credential = (request.POST.get('credential') or '').strip()
    cookie_csrf = request.COOKIES.get('g_csrf_token')
    body_csrf = request.POST.get('g_csrf_token')
    if cookie_csrf and body_csrf and cookie_csrf != body_csrf:
        return HttpResponseRedirect(f'{ret}?google_err=csrf')

    result = _google_auth_run(request, credential)
    if not result['ok']:
        code = result.get('err_code') or 'error'
        return HttpResponseRedirect(f'{ret}?google_err={code}')

    return HttpResponseRedirect(reverse('home'))


class SignupPageView(TemplateView):
    template_name = 'signup.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_google_oauth_page_context(self.request))
        return ctx


class LoginPageView(TemplateView):
    template_name = 'login.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_google_oauth_page_context(self.request))
        return ctx


def _safe_bool_env(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _build_onboarding_progress_for_user(user):
    students_qs = Student.objects.filter(user=user)
    student_count = students_qs.count()
    lesson_count = Lesson.objects.filter(student__user=user).count()
    # Financeiro/pagamentos = lançamentos criados (FinancialEntry) para alunos do professor
    financial_count = FinancialEntry.objects.filter(student__user=user).count()

    has_student = student_count > 0
    has_lesson = lesson_count > 0
    has_financial = financial_count > 0

    if not has_student:
        stage = "missing_student"
    elif not has_lesson:
        stage = "missing_lesson"
    elif not has_financial:
        stage = "missing_financial"
    else:
        stage = "activated"

    return {
        "stage": stage,
        "has_student": has_student,
        "has_lesson": has_lesson,
        "has_financial": has_financial,
        "student_count": student_count,
        "lesson_count": lesson_count,
        "financial_count": financial_count,
        # Mantido para compatibilidade com payload antigo (não usado agora)
        "has_homework": False,
        "homework_count": 0,
    }


def _trigger_n8n_onboarding_webhook(request, user):
    """
    Dispara webhook no n8n após signup/trial.
    Fire-and-forget para não bloquear o signup.
    """
    enabled = _safe_bool_env("N8N_ONBOARDING_WEBHOOK_ENABLED", default=False)
    if not enabled:
        print(
            f"[N8N onboarding] skip user_id={getattr(user, 'id', None)} "
            f"reason=disabled N8N_ONBOARDING_WEBHOOK_ENABLED={os.environ.get('N8N_ONBOARDING_WEBHOOK_ENABLED', '')!r}"
        )
        return

    webhook_url = os.environ.get("N8N_ONBOARDING_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print(
            f"[N8N onboarding] skip user_id={getattr(user, 'id', None)} "
            f"reason=empty_webhook_url"
        )
        return

    status_token = os.environ.get("N8N_ONBOARDING_STATUS_TOKEN", "").strip()
    _site = getattr(settings, "SITE_URL", "https://www.educaflowone.com.br").rstrip("/")
    check_url = f"{_site}/api/internal/onboarding/progress/"
    user_profile = getattr(user, "profile", None)
    trial_ends_at = getattr(user_profile, "trial_ends_at", None) if user_profile else None

    payload = {
        "event": "trial_started",
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at else None,
        "started_at": timezone.now().isoformat(),
        "onboarding_check_url": check_url,
        "onboarding_check_token": status_token,
    }
    print(
        f"[N8N onboarding] enqueue user_id={user.id} url={webhook_url} "
        f"check_url={check_url} status_token_len={len(status_token)}"
    )

    def _worker():
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib_request.Request(
                webhook_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib_request.urlopen(req, timeout=8) as resp:
                body = resp.read()
                print(
                    f"[N8N onboarding] success user_id={user.id} "
                    f"http_status={getattr(resp, 'status', 'unknown')} "
                    f"response_len={len(body) if body else 0}"
                )
        except Exception as e:
            print(f"[N8N onboarding] Falha ao disparar webhook: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def _n8n_internal_token_ok(request):
    """
    Valida token interno compartilhado com n8n (onboarding, trial ending, etc.).
    Aceita header X-Internal-Token ou query ?token= / ?onboarding_check_token=
    Retorna (True, None) ou (False, Response 401).
    """
    expected_token = os.environ.get("N8N_ONBOARDING_STATUS_TOKEN", "").strip()
    provided_token = (
        request.headers.get("X-Internal-Token")
        or request.query_params.get("token")
        or request.query_params.get("onboarding_check_token")
        or ""
    ).strip()
    try:
        print(
            f"[n8n_internal_token] expected_len={len(expected_token)} "
            f"provided_len={len(provided_token)} provided_empty={not bool(provided_token)}"
        )
    except Exception:
        pass
    if not expected_token or provided_token != expected_token:
        return False, Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
    return True, None


@api_view(["GET"])
@permission_classes([AllowAny])
def onboarding_progress_internal(request):
    """
    Endpoint para o n8n consultar evolução do onboarding/trial.
    Segurança: header X-Internal-Token deve bater com N8N_ONBOARDING_STATUS_TOKEN.
    """
    ok, err = _n8n_internal_token_ok(request)
    if not ok:
        return err

    raw_user_id = request.query_params.get("user_id")
    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        return Response({"detail": "user_id inválido"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"detail": "Usuário não encontrado"}, status=status.HTTP_404_NOT_FOUND)

    progress = _build_onboarding_progress_for_user(user)
    return Response({
        "user_id": user.id,
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name or "",
        **progress,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def trial_ending_users(request):
    """
    Lista usuários com trial encerrando em ~2 dias que ainda não receberam o e-mail de aviso.
    Usado pelo workflow n8n "Trial Ending" (cron diário).

    Janela: trial_ends_at entre now+44h e now+52h (~2 dias, com folga).
    Filtros: trial_ending_email_sent_at vazio, não exempt, sem Subscription ativa.

    Auth: mesmo token de N8N_ONBOARDING_STATUS_TOKEN (header ou query).
    """
    ok, err = _n8n_internal_token_ok(request)
    if not ok:
        return err

    now = timezone.now()
    window_start = now + timedelta(hours=44)
    window_end = now + timedelta(hours=52)

    active_sub_user_ids = Subscription.objects.filter(
        status=Subscription.STATUS_ACTIVE
    ).values_list("user_id", flat=True)

    profiles = (
        UserProfile.objects.select_related("user")
        .filter(
            trial_ends_at__gte=window_start,
            trial_ends_at__lte=window_end,
            trial_ending_email_sent_at__isnull=True,
            subscription_exempt=False,
        )
        .exclude(user_id__in=active_sub_user_ids)
    )

    users = []
    for profile in profiles:
        users.append(
            {
                "user_id": profile.user.id,
                "email": profile.user.email,
                "first_name": profile.user.first_name or "",
                "username": profile.user.username,
                "trial_ends_at": profile.trial_ends_at.isoformat()
                if profile.trial_ends_at
                else None,
            }
        )

    return Response({"users": users})


@api_view(["POST"])
@permission_classes([AllowAny])
def mark_trial_email_sent(request):
    """
    Marca trial_ending_email_sent_at após o n8n enviar o e-mail de fim de trial.
    Body JSON: {"user_id": 123}

    Auth: mesmo token de N8N_ONBOARDING_STATUS_TOKEN (header ou query).
    """
    ok, err = _n8n_internal_token_ok(request)
    if not ok:
        return err

    raw_user_id = request.data.get("user_id")
    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        return Response({"detail": "user_id inválido"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(user_id=user_id)
    except UserProfile.DoesNotExist:
        return Response({"detail": "UserProfile não encontrado"}, status=status.HTTP_404_NOT_FOUND)

    profile.trial_ending_email_sent_at = timezone.now()
    profile.save(update_fields=["trial_ending_email_sent_at"])

    return Response({"success": True})


# ==========================
# Dashboard Summary API
# ==========================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary_view(request):
    """
    Endpoint para fornecer dados do dashboard inicial.
    Retorna KPIs, lista de hoje, alertas e resumo do mês.
    """
    try:
        user = request.user
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        # Calcular o último dia do mês atual
        if today.month == 12:
            current_month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            current_month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        next_3_days = today + timedelta(days=3)
        
        # Filtrar dados do usuário (considerando professores parceiros)
        try:
            is_admin = user.profile.is_admin
            user_profile = user.profile.user_profile
        except UserProfile.DoesNotExist:
            is_admin = False
            user_profile = None
        
        # IDs de usuários para filtrar
        # IMPORTANTE: Por enquanto, mostrar apenas dados do usuário atual
        # Se precisar incluir parceiros no futuro, descomentar o código abaixo
        user_ids = [user.id]
        
        # NOTA: Desabilitado temporariamente para evitar mostrar dados de outros usuários
        # if user_profile == UserProfile.PROFILE_TEACHER:
        #     try:
        #         partner_ids = list(user.profile.partner_teachers.values_list('user_id', flat=True))
        #         user_ids.extend(partner_ids)
        #     except:
        #         pass
        
        # Base queryset do financeiro (mesma lógica da tela /financeiro/)
        financial_base = get_financial_entries_queryset_for_user(request)
        
        # ===== KPIs =====
        # Aulas hoje
        today_lessons = Lesson.objects.filter(
            user_id__in=user_ids,
            date=today
        )
        today_classes = today_lessons.count()
        today_pending = today_lessons.filter(status='pending').count()
        
        # Canceladas no mês
        month_canceled = Lesson.objects.filter(
            user_id__in=user_ids,
            date__gte=current_month_start,
            date__lte=today,
            status='canceled'
        ).count()
        
        # Alunos ativos
        active_students = Student.objects.filter(
            user_id__in=user_ids,
            status=Student.STATUS_ACTIVE
        ).count()
        
        # ===== Contagens do Calendário (para Visão Rápida) =====
        # Todas as aulas do usuário (sem filtro de data)
        all_lessons = Lesson.objects.filter(user_id__in=user_ids)
        
        # Aulas confirmadas (status="confirmed" e não realizadas)
        calendar_confirmed = all_lessons.filter(
            status='confirmed',
            realized=False
        ).count()
        
        # Pendências do mês (status="pending" e não realizadas, do mês atual)
        calendar_pending_month = all_lessons.filter(
            date__gte=current_month_start,
            date__lte=current_month_end,
            status='pending',
            realized=False
        ).count()
        
        # Aulas realizadas (realized=True)
        calendar_realized = all_lessons.filter(realized=True).count()
        
        # Financeiro - mesmos critérios da tela /financeiro/
        # A receber hoje: vencimentos do dia, pendentes ou vencidos
        due_today_entries = financial_base.filter(
            due_date=today,
            status__in=[FinancialEntry.STATUS_PENDING, FinancialEntry.STATUS_OVERDUE]
        )
        due_today_amount = due_today_entries.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Em atraso: vencidos do mês atual (igual ao financeiro - só entradas com vencimento no mês)
        overdue_entries = financial_base.filter(
            due_date__gte=current_month_start,
            due_date__lte=current_month_end,
            due_date__lt=today,
            status__in=[FinancialEntry.STATUS_PENDING, FinancialEntry.STATUS_OVERDUE]
        )
        overdue_amount = overdue_entries.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Recebido no mês: parcelas com vencimento no mês que foram pagas (igual ao financeiro)
        paid_month_entries = financial_base.filter(
            due_date__gte=current_month_start,
            due_date__lte=current_month_end,
            status=FinancialEntry.STATUS_PAID
        )
        paid_month_amount = paid_month_entries.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # ===== Lista "Hoje" =====
        today_items = []
        
        # Aulas de hoje (até 3)
        lessons_today = today_lessons.select_related('student').order_by('time')[:3]
        for lesson in lessons_today:
            time_str = lesson.time.strftime('%H:%M') if lesson.time else '-'
            status_badge = 'good' if lesson.status == 'confirmed' else ('warn' if lesson.status == 'pending' else 'bad')
            status_label = 'Confirmado' if lesson.status == 'confirmed' else ('Pendente' if lesson.status == 'pending' else 'Cancelado')
            
            meta = []
            if lesson.title:
                meta.append(f"📘 {lesson.title}")
            
            today_items.append({
                'time': time_str,
                'title': f'Aula • {lesson.student.name}',
                'badges': [{'type': status_badge, 'label': status_label}],
                'meta': meta
            })
        
        # Cobrança vencendo hoje (se não tiver 3 aulas já)
        if len(today_items) < 3:
            billing_today = due_today_entries.select_related('student').first()
            if billing_today:
                today_items.append({
                    'time': '-',
                    'title': f'Cobrança • {billing_today.student.name}',
                    'badges': [{'type': 'warn', 'label': 'Vence hoje'}],
                    'meta': [f'💳 R$ {billing_today.amount:.2f}'.replace('.', ','), '📲 WhatsApp']
                })
        
        # ===== Alertas =====
        alerts = []
        
        # Alerta 1: Cobranças em atraso
        overdue_count = overdue_entries.count()
        if overdue_count > 0:
            alerts.append({
                'type': 'bad',
                'title': f'{overdue_count} cobrança{"s" if overdue_count > 1 else ""} em atraso',
                'description': 'Enviar agora aumenta muito a chance de pagamento hoje.'
            })
        
        # Alerta 2: Vencimentos próximos (próximos 3 dias)
        upcoming_entries = financial_base.filter(
            due_date__gt=today,
            due_date__lte=next_3_days,
            status__in=[FinancialEntry.STATUS_PENDING, FinancialEntry.STATUS_OVERDUE]
        )
        upcoming_count = upcoming_entries.count()
        if upcoming_count > 0:
            alerts.append({
                'type': 'warn',
                'title': f'Vencimentos próximos (3 dias)',
                'description': 'Prepare as cobranças antes do prazo e evite "correria de última hora".'
            })
        
        # ===== Resumo do mês =====
        # Taxa de confirmação - APENAS aulas do usuário logado
        month_lessons = Lesson.objects.filter(
            user_id__in=user_ids,
            date__gte=current_month_start,
            date__lte=today
        )
        
        total_month_lessons = month_lessons.exclude(status='canceled').count()
        confirmed_month_lessons = month_lessons.filter(status='confirmed').count()
        confirmation_rate = (confirmed_month_lessons / total_month_lessons * 100) if total_month_lessons > 0 else 0
        
        # Pendente no mês - mesmos critérios do financeiro
        pending_month_entries = financial_base.filter(
            due_date__gte=current_month_start,
            due_date__lte=current_month_end,
            status__in=[FinancialEntry.STATUS_PENDING, FinancialEntry.STATUS_OVERDUE]
        )
        
        pending_month_amount = pending_month_entries.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Tarefas abertas
        tasks_open = Task.objects.filter(
            user_id__in=user_ids,
            status__in=['todo', 'doing']
        ).count()
        
        # Reagendamentos (aulas canceladas no mês)
        reschedules = month_canceled
        
        # Buscar foto do perfil e flag de boas-vindas
        user_photo = None
        welcome_dismissed_forever = False
        try:
            if user.profile.photo:
                user_photo = user.profile.photo.url
            welcome_dismissed_forever = getattr(user.profile, 'welcome_dismissed_forever', False)
        except Exception:
            pass
        
        # Montar resposta
        response_data = {
            'user': {
                'name': user.get_full_name() or user.username,
                'email': user.email or '',
                'photo': user_photo,
                'welcome_dismissed_forever': welcome_dismissed_forever,
            },
            'kpis': {
                'today_classes': today_classes,
                'today_pending': today_pending,
                'month_canceled': month_canceled,
                'active_students': active_students,
                'due_today_amount': float(due_today_amount),
                'overdue_amount': float(overdue_amount),
                'paid_month_amount': float(paid_month_amount),
                # Contagens do calendário (para Visão Rápida)
                'calendar_confirmed': calendar_confirmed,
                'calendar_pending_month': calendar_pending_month,
                'calendar_realized': calendar_realized
            },
            'today': {
                'items': today_items
            },
            'alerts': alerts,
            'month_summary': {
                'confirmation_rate': round(confirmation_rate, 1),
                'confirmation_rate_target': 90,
                'pending_amount': float(pending_month_amount),
                'paid_amount': float(paid_month_amount),
                'tasks_open': tasks_open,
                'reschedules': reschedules
            }
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao carregar dados do dashboard: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==========================
# Unread Homework Messages API
# ==========================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_unread_homework_messages(request):
    """
    Retorna notificações (sininho) com mensagens de homework enviadas pelo aluno
    que ainda não foram marcadas como "lidas" pelo professor logado.
    """
    try:
        user = request.user

        # Mesma regra do detalhe do aluno / StudentViewSet (dono, parceiro, admin).
        try:
            is_admin = user.profile.is_admin
            user_profile = user.profile.user_profile
        except UserProfile.DoesNotExist:
            is_admin = False
            user_profile = None

        if is_admin:
            students_qs = Student.objects.select_related("user", "assigned_teacher").all()
        elif user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
            students_qs = (
                Student.objects.select_related("user", "assigned_teacher")
                .filter(user__profile__partner_teachers=user.profile)
                .filter(assigned_teacher=user)
            )
        else:
            students_qs = Student.objects.select_related("user", "assigned_teacher").filter(user=user)

        unread_qs = (
            StudentHomeworkMessage.objects.filter(
                sender=StudentHomeworkMessage.SENDER_STUDENT,
                homework__student__in=students_qs,
            )
            .exclude(reads__user=user)
            .select_related("homework", "homework__student")
            .order_by("-created_at", "-id")
        )

        # Contagem total de mensagens não lidas (para o badge do dashboard).
        unread_count = unread_qs.count()

        # Agrupar por aluno: 1 card por aluno, exibindo quantas mensagens não lidas cada um tem.
        grouped = (
            unread_qs.values("homework__student_id", "homework__student__name")
            .annotate(
                unread_messages=Count("id"),
                latest_created_at=Max("created_at"),
            )
            .order_by("-latest_created_at")
        )

        unread_students_total = grouped.count()
        limit = 8
        grouped_items = list(grouped[:limit])

        msg_items = [
            {
                "student_id": row["homework__student_id"],
                "student_name": row["homework__student__name"],
                "unread_count": row["unread_messages"],
                "url": f"/alunos/{row['homework__student_id']}/",
            }
            for row in grouped_items
        ]

        return Response(
            {
                "unread_count": unread_count,
                "unread_students_count": unread_students_total,
                "items": msg_items,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao carregar notificações: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ==========================
# Profile API
# ==========================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_get_view(request):
    """
    Endpoint para obter dados do perfil do usuário atual.
    Acessível para todos os usuários logados (não apenas admins).
    """
    try:
        user = request.user
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            # Criar perfil se não existir
            profile = UserProfile.objects.create(
                user=user,
                user_profile=UserProfile.PROFILE_TEACHER,
                is_admin=False
            )
        
        serializer = ProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao carregar perfil: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_partner_teachers_lookup(request):
    """
    Busca um usuário por e-mail para vincular como professor parceiro.
    Apenas usuários com perfil Professor podem usar. Retorna usuários com perfil Prof. Parceiro.
    GET /api/profile/partner-teachers/lookup/?email=xxx@yy.com
    """
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return Response(
            {'error': 'Perfil não encontrado'},
            status=status.HTTP_403_FORBIDDEN
        )
    if profile.user_profile != UserProfile.PROFILE_TEACHER:
        return Response(
            {'error': 'Apenas professores (dono da conta) podem vincular professores parceiros.'},
            status=status.HTTP_403_FORBIDDEN
        )
    email = (request.GET.get('email') or '').strip().lower()
    if not email:
        return Response(
            {'error': 'Informe o parâmetro email.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return Response(
            {'error': 'Nenhum usuário encontrado com este e-mail.'},
            status=status.HTTP_404_NOT_FOUND
        )
    try:
        up = user.profile
        if up.user_profile != UserProfile.PROFILE_PARTNER_TEACHER:
            return Response(
                {'error': 'Este usuário não é um professor parceiro. Apenas perfis "Prof. Parceiro" podem ser vinculados.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    except UserProfile.DoesNotExist:
        return Response(
            {'error': 'Perfil do usuário não encontrado.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if user.id == request.user.id:
        return Response(
            {'error': 'Você não pode se vincular a si mesmo.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    return Response({
        'id': user.id,
        'username': user.username,
        'name': user.get_full_name() or user.username,
        'email': user.email or '',
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def profile_partner_teachers_create(request):
    """
    Cadastra um novo professor parceiro e já vincula ao professor atual.
    Apenas usuários com perfil Professor podem usar.
    Body: email, first_name, last_name, password, password_confirm [, username ]
    """
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return Response(
            {'error': 'Perfil não encontrado'},
            status=status.HTTP_403_FORBIDDEN
        )
    if profile.user_profile != UserProfile.PROFILE_TEACHER:
        return Response(
            {'error': 'Apenas professores (dono da conta) podem cadastrar professores parceiros.'},
            status=status.HTTP_403_FORBIDDEN
        )
    data = request.data
    email = (data.get('email') or '').strip()
    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()
    password = data.get('password') or ''
    password_confirm = data.get('password_confirm') or data.get('password') or ''
    username = (data.get('username') or '').strip()

    if not email:
        return Response(
            {'error': 'E-mail é obrigatório.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not password or len(password) < 8:
        return Response(
            {'error': 'Senha é obrigatória e deve ter pelo menos 8 caracteres.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if password != password_confirm:
        return Response(
            {'error': 'As senhas não coincidem.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if User.objects.filter(email__iexact=email).exists():
        return Response(
            {'error': 'Já existe um usuário com este e-mail.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not username:
        # Username = caracteres antes do @ (ex: jonasbarros99@gmail.com -> jonasbarros99)
        username = (email.split('@')[0] if '@' in email else email).strip().lower()[:150]
        if not username:
            username = 'user'
    if User.objects.filter(username=username).exists():
        base = username[:120]
        for i in range(1, 100):
            username = base + str(i)
            if not User.objects.filter(username=username).exists():
                break
        else:
            return Response(
                {'error': 'Não foi possível gerar um nome de usuário único.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        # Verificar limite de professores parceiros do plano (trial: sem limite)
        if not _user_is_in_trial(request.user):
            try:
                subscription = request.user.subscription
                _sync_subscription_from_stripe(subscription)
                subscription.refresh_from_db()
                if subscription.is_active:
                    max_partners = subscription.get_max_partner_teachers()
                    if max_partners is not None:
                        current_count = profile.partner_teachers.count()
                        if current_count >= max_partners:
                            user.delete()
                            return Response(
                                {'error': f'Limite de {max_partners} professores parceiros atingido no plano {subscription.get_tier_display()}. '
                                         f'Faça upgrade para Platinum para parceiros ilimitados.'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
            except Subscription.DoesNotExist:
                pass
        
        partner_profile = UserProfile.objects.create(
            user=user,
            user_profile=UserProfile.PROFILE_PARTNER_TEACHER,
            is_admin=False,
        )
        profile.partner_teachers.add(partner_profile)
        return Response({
            'id': user.id,
            'username': user.username,
            'name': user.get_full_name() or user.username,
            'email': user.email or '',
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE', 'POST'])
@permission_classes([IsAuthenticated])
def profile_partner_teachers_remove(request, user_id):
    """
    Desvincula um professor parceiro (acesso cortado imediatamente).
    Apenas perfil Professor. O parceiro deixa de ver alunos/aulas deste professor.
    DELETE /api/profile/partner-teachers/<user_id>/remove/ ou POST com _method=DELETE
    """
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return Response(
            {'error': 'Perfil não encontrado'},
            status=status.HTTP_403_FORBIDDEN
        )
    if profile.user_profile != UserProfile.PROFILE_TEACHER:
        return Response(
            {'error': 'Apenas professores (dono da conta) podem desvincular parceiros.'},
            status=status.HTTP_403_FORBIDDEN
        )
    try:
        partner_profile = UserProfile.objects.get(
            user_id=user_id,
            user_profile=UserProfile.PROFILE_PARTNER_TEACHER,
        )
    except UserProfile.DoesNotExist:
        return Response(
            {'error': 'Usuário não encontrado ou não é professor parceiro.'},
            status=status.HTTP_404_NOT_FOUND
        )
    profile.partner_teachers.remove(partner_profile)
    # Cortar acesso: tirar o parceiro dos alunos que ele estava atribuído (dono = request.user)
    Student.objects.filter(
        user=request.user,
        assigned_teacher_id=user_id
    ).update(assigned_teacher=None)
    # Não alterar lançamentos financeiros: manter user/beneficiary como estão para o professor dono conservar o histórico (quanto pagou ao parceiro, etc.). O parceiro deixa de vê-los por filtro (partner_teachers).
    # Inativar o usuário do parceiro se não estiver vinculado a nenhum outro professor (não consegue mais logar)
    still_linked = UserProfile.objects.filter(
        user_profile=UserProfile.PROFILE_TEACHER,
        partner_teachers=partner_profile,
    ).exists()
    if not still_linked:
        User.objects.filter(id=user_id).update(is_active=False)
    return Response({'success': True, 'message': 'Professor parceiro desvinculado. Acesso cortado imediatamente.'}, status=status.HTTP_200_OK)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def profile_partner_teachers_update(request, user_id):
    """
    Atualiza dados de um professor parceiro vinculado (nome, e-mail, senha).
    Apenas perfil Professor pode editar seus parceiros.
    """
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return Response(
            {'error': 'Perfil não encontrado'},
            status=status.HTTP_403_FORBIDDEN
        )
    if profile.user_profile != UserProfile.PROFILE_TEACHER:
        return Response(
            {'error': 'Apenas professores (dono da conta) podem editar parceiros.'},
            status=status.HTTP_403_FORBIDDEN
        )
    if not profile.partner_teachers.filter(user_id=user_id).exists():
        return Response(
            {'error': 'Este professor parceiro não está vinculado a você.'},
            status=status.HTTP_404_NOT_FOUND
        )
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {'error': 'Usuário não encontrado.'},
            status=status.HTTP_404_NOT_FOUND
        )
    data = request.data
    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    password_confirm = data.get('password_confirm') or data.get('password') or ''

    if email and User.objects.filter(email__iexact=email).exclude(id=user_id).exists():
        return Response(
            {'error': 'Já existe outro usuário com este e-mail.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if password or password_confirm:
        if len(password) < 8:
            return Response(
                {'error': 'A senha deve ter pelo menos 8 caracteres.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if password != password_confirm:
            return Response(
                {'error': 'As senhas não coincidem.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if email:
        user.email = email
    if password:
        user.set_password(password)
    user.save()
    return Response({
        'id': user.id,
        'username': user.username,
        'name': user.get_full_name() or user.username,
        'email': user.email or '',
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def welcome_dismiss_view(request):
    """
    Marca que o usuário não deseja mais ver o popup de boas-vindas.
    Usado quando o usuário marca "Não mostrar novamente" e fecha o modal.
    """
    try:
        user = request.user
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(
            user=user,
            user_profile=UserProfile.PROFILE_TEACHER,
            is_admin=False
        )
    profile.welcome_dismissed_forever = True
    profile.save(update_fields=['welcome_dismissed_forever'])
    return Response({'success': True}, status=status.HTTP_200_OK)


@api_view(['POST', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_update_view(request):
    """
    Endpoint para atualizar dados do perfil do usuário atual.
    Acessível para todos os usuários logados (podem editar apenas seu próprio perfil).
    """
    try:
        user = request.user
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            # Criar perfil se não existir
            profile = UserProfile.objects.create(
                user=user,
                user_profile=UserProfile.PROFILE_TEACHER,
                is_admin=False
            )
        
        # Preparar dados para o serializer
        # request.data pode ser QueryDict (FormData) ou dict (JSON)
        raw_data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        
        # Log para debug
        import logging
        logger = logging.getLogger(__name__)
        print(f"[DEBUG] Profile update - raw data recebido: {raw_data}")
        print(f"[DEBUG] Profile update - request.FILES: {request.FILES}")
        logger.info(f"Profile update - raw data: {raw_data}")
        
        # Transformar dados planos - agora os campos do User vão direto (não mais aninhados)
        serializer_data = {}
        
        # Dados do User - incluir diretamente (não mais aninhados)
        if 'email' in raw_data:
            serializer_data['email'] = raw_data.get('email', '') or ''
        if 'first_name' in raw_data:
            serializer_data['first_name'] = raw_data.get('first_name', '') or ''
        if 'last_name' in raw_data:
            serializer_data['last_name'] = raw_data.get('last_name', '') or ''
        
        # Agenda pública: apenas Premium+, admin ou subscription_exempt
        public_calendar_fields = ['slug_publico', 'agenda_publica_ativa', 'public_availability', 'public_booking_duration']
        if any(f in raw_data for f in public_calendar_fields) and not _user_can_use_public_calendar(user):
            return Response(
                {'error': 'A agenda pública é um recurso disponível no plano Premium ou superior. Faça upgrade para utilizar.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Campos diretos do UserProfile - incluir apenas os que foram enviados
        profile_fields = ['cpf_cnpj', 'phone', 'cep', 'address', 'city', 'state', 'timezone', 'language',
                         'slug_publico', 'agenda_publica_ativa', 'public_availability', 'public_booking_duration']
        for field in profile_fields:
            if field in raw_data:
                val = raw_data.get(field)
                if field == 'slug_publico':
                    serializer_data[field] = (val or '').strip() or None
                elif field == 'agenda_publica_ativa':
                    serializer_data[field] = bool(val in (True, 'true', '1', 1))
                elif field == 'public_availability':
                    serializer_data[field] = val if isinstance(val, dict) else {}
                elif field == 'public_booking_duration':
                    try:
                        serializer_data[field] = int(val) if val is not None else 60
                    except (ValueError, TypeError):
                        serializer_data[field] = 60
                else:
                    serializer_data[field] = val or ''
        
        # Foto - processar se foi enviada via FormData (request.FILES)
        # Se não houver foto em FILES, mas houver em data (pode ser string vazia), não incluir
        if 'photo' in request.FILES:
            serializer_data['photo'] = request.FILES['photo']
            print(f"[DEBUG] Foto recebida via FILES: {request.FILES['photo'].name}, tamanho: {request.FILES['photo'].size}")
        elif 'photo' in raw_data and raw_data.get('photo'):
            # Se vier como string (JSON), pode ser uma URL ou path existente - não processar
            print(f"[DEBUG] Foto em raw_data (ignorando, deve vir via FILES): {raw_data.get('photo')}")
        
        # Senhas - só incluir se foram fornecidas
        if raw_data.get('password') and raw_data.get('password').strip():
            serializer_data['password'] = raw_data.get('password')
            serializer_data['password_confirm'] = raw_data.get('password_confirm', raw_data.get('password'))
        
        # Professores parceiros: só para perfil Professor (não prof. parceiro)
        if profile.user_profile == UserProfile.PROFILE_TEACHER:
            ids = None
            if hasattr(request.data, 'getlist'):
                ids = request.data.getlist('partner_teachers_ids')
            if ids is None:
                ids = raw_data.get('partner_teachers_ids', [])
            if isinstance(ids, list):
                serializer_data['partner_teachers_ids'] = [int(x) for x in ids if x not in (None, '')]
            else:
                serializer_data['partner_teachers_ids'] = []
        
        print(f"[DEBUG] Profile update - serializer data preparado: {serializer_data}")
        print(f"[DEBUG] Profile atual antes: email={user.email}, first_name={user.first_name}, last_name={user.last_name}")
        print(f"[DEBUG] UserProfile atual antes: cpf_cnpj={profile.cpf_cnpj}, phone={profile.phone}, city={profile.city}")
        logger.info(f"Profile update - serializer data: {serializer_data}")
        
        serializer = ProfileSerializer(profile, data=serializer_data, partial=True)
        
        print(f"[DEBUG] Serializer is_valid: {serializer.is_valid()}")
        if not serializer.is_valid():
            print(f"[DEBUG] Serializer errors: {serializer.errors}")
            logger.error(f"Serializer errors: {serializer.errors}")
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Salvar
        try:
            print(f"[DEBUG] Chamando serializer.save()...")
            updated_instance = serializer.save()
            print(f"[DEBUG] serializer.save() retornou")
            
            # Recarregar do banco para garantir que temos os dados atualizados
            print(f"[DEBUG] Recarregando do banco...")
            updated_instance.refresh_from_db()
            updated_instance.user.refresh_from_db()
            
            print(f"[DEBUG] Profile atualizado: email={updated_instance.user.email}, first_name={updated_instance.user.first_name}, last_name={updated_instance.user.last_name}")
            print(f"[DEBUG] UserProfile atualizado: cpf_cnpj={updated_instance.cpf_cnpj}, phone={updated_instance.phone}, city={updated_instance.city}")
            print(f"[DEBUG] Perfil salvo com sucesso")
            
            # Retornar dados atualizados do serializer
            response_data = ProfileSerializer(updated_instance).data
            print(f"[DEBUG] Dados retornados no response: {response_data}")
            
            return Response({
                'success': True,
                'message': 'Perfil atualizado com sucesso',
                'data': response_data
            }, status=status.HTTP_200_OK)
        except Exception as save_error:
            print(f"[DEBUG] Erro ao salvar: {str(save_error)}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Erro ao salvar: {str(save_error)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response(
            {'error': f'Erro ao atualizar perfil: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==========
# Calendar API Endpoints
# ==========

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def calendar_events(request):
    """
    GET /api/calendar/events/?start=YYYY-MM-DD&end=YYYY-MM-DD
    Retorna eventos (lessons) no período especificado.
    Formato de retorno: [{id, date:"YYYY-MM-DD", time:"HH:MM", student:"Nome", status:"confirmed|pending|cancelled|done", note:""}]
    """
    try:
        start_str = request.query_params.get('start')
        end_str = request.query_params.get('end')
        
        if not start_str or not end_str:
            return Response(
                {'error': 'Parâmetros start e end são obrigatórios (formato: YYYY-MM-DD)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        
        # Filtrar lessons do usuário no período
        qs = Lesson.objects.filter(
            user=request.user,
            date__gte=start_date,
            date__lte=end_date
        ).select_related('student').order_by('date', 'time')
        
        # Verificar se é admin ou professor principal (ver outras lessons)
        try:
            is_admin = request.user.profile.is_admin
            user_profile = request.user.profile.user_profile
            if not is_admin and user_profile == UserProfile.PROFILE_TEACHER:
                # Prof. Principal vê todas as aulas dos seus alunos (mantém histórico mesmo após desvincular parceiro)
                qs = Lesson.objects.filter(
                    student__user=request.user,
                    date__gte=start_date,
                    date__lte=end_date
                ).select_related('student').order_by('date', 'time')
            elif not is_admin and user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                # Parceiro só vê aulas de alunos ATRIBUÍDOS a ele (assigned_teacher)
                qs = qs.filter(student__user__profile__partner_teachers=request.user.profile).filter(student__assigned_teacher=request.user)
        except UserProfile.DoesNotExist:
            pass
        
        events = []
        for lesson in qs:
            # Determinar status: se realized=True, status é "done", senão usa o status normal
            lesson_status = "done" if lesson.realized else lesson.status
            # Mapear status do modelo para o formato esperado pelo frontend
            status_map = {
                "confirmed": "confirmed",
                "pending": "pending",
                "canceled": "cancelled",  # Note: modelo usa "canceled", frontend espera "cancelled"
            }
            if lesson_status == "done":
                final_status = "done"
            else:
                final_status = status_map.get(lesson_status, "pending")
            
            time_str = lesson.time.strftime('%H:%M') if lesson.time else ""
            
            events.append({
                'id': lesson.id,
                'date': lesson.date.strftime('%Y-%m-%d'),
                'time': time_str,
                'student': lesson.student.name,
                'student_id': lesson.student.id,
                'status': final_status,
                'realized': lesson.realized,
                'note': lesson.info or "",
                'source': 'lesson'
            })
        
        # Incluir solicitações da agenda pública (pendentes) - para professor dono ou admin
        try:
            is_admin = getattr(request.user.profile, 'is_admin', False)
            user_profile = getattr(request.user.profile, 'user_profile', None)
            if is_admin or user_profile != UserProfile.PROFILE_PARTNER_TEACHER:
                pbr_qs = PublicBookingRequest.objects.filter(
                    teacher=request.user,
                    status=PublicBookingRequest.STATUS_PENDING,
                    requested_date__gte=start_date,
                    requested_date__lte=end_date
                ).order_by('requested_date', 'requested_time')
                for pbr in pbr_qs:
                    events.append({
                        'id': f'pbr_{pbr.id}',
                        'date': pbr.requested_date.strftime('%Y-%m-%d'),
                        'time': pbr.requested_time.strftime('%H:%M'),
                        'student': pbr.student_name,
                        'student_id': None,
                        'status': 'pending',
                        'realized': False,
                        'note': (pbr.notes or '') + (f' | WhatsApp: {pbr.student_whatsapp}' if pbr.student_whatsapp else ''),
                        'source': 'public_booking',
                        'student_email': pbr.student_email,
                        'student_whatsapp': pbr.student_whatsapp,
                        'subject': pbr.subject or '',
                    })
        except (UserProfile.DoesNotExist, AttributeError):
            pass
        
        # Ordenar eventos por data e horário
        events.sort(key=lambda e: (e['date'], e['time']))
        
        return Response(events)
    
    except ValueError as e:
        return Response(
            {'error': f'Formato de data inválido: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Erro ao buscar eventos: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def calendar_event_status(request, event_id):
    """
    PATCH /api/calendar/events/{id}/status/
    Body: {status:"confirmed|pending|cancelled|done"}
    Atualiza status de uma aula (lesson).
    """
    try:
        lesson = Lesson.objects.select_related('student', 'student__user__profile').filter(id=event_id).first()
        if not lesson:
            return Response(
                {'error': 'Aula não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        # Verificar permissão (admin ou professor principal pode editar suas e dos parceiros; parceiro só se ainda vinculado)
        try:
            is_admin = request.user.profile.is_admin
            user_profile = request.user.profile.user_profile
            if is_admin:
                pass
            elif user_profile == UserProfile.PROFILE_TEACHER:
                # Prof. dono pode editar qualquer aula dos seus alunos (mantém histórico)
                if lesson.student.user_id != request.user.id:
                    return Response(
                        {'error': 'Sem permissão para editar esta aula'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            elif user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                if lesson.student.assigned_teacher_id != request.user.id or not lesson.student.user.profile.partner_teachers.filter(user=request.user).exists():
                    return Response(
                        {'error': 'Sem permissão para editar esta aula'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            else:
                if lesson.user_id != request.user.id:
                    return Response(
                        {'error': 'Sem permissão para editar esta aula'},
                        status=status.HTTP_403_FORBIDDEN
                    )
        except UserProfile.DoesNotExist:
            if lesson.user_id != request.user.id:
                return Response(
                    {'error': 'Sem permissão para editar esta aula'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        new_status = request.data.get('status')
        if not new_status:
            return Response(
                {'error': 'Campo status é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mapear status do frontend para o modelo
        # Frontend: "done" -> realized=True, outros -> status normal
        if new_status == "done":
            lesson.realized = True
            # Manter o status original (confirmed/pending/canceled)
        else:
            lesson.realized = False
            # Mapear "cancelled" (frontend) para "canceled" (modelo)
            status_map = {
                "confirmed": "confirmed",
                "pending": "pending",
                "cancelled": "canceled",
            }
            lesson.status = status_map.get(new_status, "pending")
        
        lesson.save()
        
        # Retornar evento atualizado
        time_str = lesson.time.strftime('%H:%M') if lesson.time else ""
        final_status = "done" if lesson.realized else lesson.status
        status_map_back = {
            "confirmed": "confirmed",
            "pending": "pending",
            "canceled": "cancelled",
        }
        if final_status == "done":
            response_status = "done"
        else:
            response_status = status_map_back.get(final_status, "pending")
        
        return Response({
            'id': lesson.id,
            'date': lesson.date.strftime('%Y-%m-%d'),
            'time': time_str,
            'student': lesson.student.name,
            'student_id': lesson.student.id,
            'status': response_status,
            'realized': lesson.realized,
            'status': response_status,
            'note': lesson.info or ""
        })
    
    except Exception as e:
        return Response(
            {'error': f'Erro ao atualizar status: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calendar_event_create(request):
    """
    POST /api/calendar/events/
    Body: {date, time, student_id, status?, note?, user_id?}
    Cria uma nova aula (lesson). Professor dono ou parceiro pode criar; user_id opcional (apenas dono) para atribuir a si ou a um parceiro.
    Parceiros agendam apenas para alunos atribuídos a eles.
    """
    try:
        is_partner = False
        try:
            is_partner = request.user.profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
        except UserProfile.DoesNotExist:
            pass

        date_str = request.data.get('date')
        time_str = request.data.get('time', '')
        student_id = request.data.get('student_id')
        user_id = request.data.get('user_id')  # opcional: professor da aula (self ou parceiro)
        status_val = request.data.get('status', 'pending')
        note = request.data.get('note', '')
        
        if not date_str or not student_id:
            return Response(
                {'error': 'Campos date e student_id são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Definir professor da aula: user_id válido (self ou parceiro) ou request.user
        # Parceiros sempre criam para si mesmos
        teacher_user = request.user
        if user_id is not None and not is_partner:
            try:
                user_id = int(user_id)
            except (TypeError, ValueError):
                return Response(
                    {'error': 'user_id inválido'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                profile = request.user.profile
                if profile.user_profile == UserProfile.PROFILE_TEACHER:
                    partner_ids = list(profile.partner_teachers.values_list('user_id', flat=True))
                    if user_id == request.user.id or user_id in partner_ids:
                        teacher_user = User.objects.get(id=user_id)
                    else:
                        return Response(
                            {'error': 'Professor selecionado não é permitido para esta conta.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                elif user_id != request.user.id:
                    return Response(
                        {'error': 'Professor selecionado não é permitido.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except User.DoesNotExist:
                return Response(
                    {'error': 'Professor não encontrado.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Aluno: admin vê todos; dono vê alunos da conta; parceiro vê apenas alunos atribuídos a ele
        try:
            profile = request.user.profile
            if getattr(profile, 'is_admin', False):
                student = Student.objects.get(id=student_id)
            elif profile.user_profile == UserProfile.PROFILE_TEACHER:
                partner_ids = list(profile.partner_teachers.values_list('user_id', flat=True))
                partner_ids.append(request.user.id)
                student = Student.objects.get(id=student_id, user_id__in=partner_ids)
            else:
                # Parceiro: apenas alunos atribuídos a ele
                student = Student.objects.get(id=student_id, assigned_teacher=request.user)
        except Student.DoesNotExist:
            return Response(
                {'error': 'Aluno não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except UserProfile.DoesNotExist:
            student = Student.objects.get(id=student_id, user=request.user)

        # Dono atribuindo aula a parceiro: aluno deve estar vinculado ao parceiro
        if teacher_user.id != request.user.id and student.assigned_teacher_id != teacher_user.id:
            return Response({
                'student_assignment': 'O aluno não está vinculado a este professor parceiro. Atribua o aluno ao professor na tela de Alunos antes de agendar a aula.',
                'student_name': student.name,
                'teacher_name': teacher_user.get_full_name() or teacher_user.username,
            }, status=status.HTTP_400_BAD_REQUEST)

        lesson_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        lesson_time = None
        if time_str:
            try:
                lesson_time = datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                return Response(
                    {'error': 'Formato de horário inválido (use HH:MM)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Mapear status
        realized = False
        lesson_status = "pending"
        if status_val == "done":
            realized = True
            lesson_status = "pending"  # Status padrão quando marcado como realizado
        else:
            status_map = {
                "confirmed": "confirmed",
                "pending": "pending",
                "cancelled": "canceled",
            }
            lesson_status = status_map.get(status_val, "pending")
        
        # Criar lesson (user = professor da aula)
        lesson = Lesson.objects.create(
            student=student,
            user=teacher_user,
            date=lesson_date,
            time=lesson_time,
            title=f"Aula {student.name}",
            info=note,
            status=lesson_status,
            realized=realized
        )
        
        # Retornar evento criado
        time_str_resp = lesson.time.strftime('%H:%M') if lesson.time else ""
        response_status = "done" if lesson.realized else status_val
        
        return Response({
            'id': lesson.id,
            'date': lesson.date.strftime('%Y-%m-%d'),
            'time': time_str_resp,
            'student': lesson.student.name,
            'student_id': lesson.student.id,
            'status': response_status,
            'note': lesson.info or ""
        }, status=status.HTTP_201_CREATED)
    
    except ValueError as e:
        return Response(
            {'error': f'Formato de data inválido: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Erro ao criar aula: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def calendar_event_update(request, event_id):
    """
    PUT/PATCH /api/calendar/events/{id}/
    Body: {date:"YYYY-MM-DD", time:"HH:MM", student_id:123, status:"confirmed|pending|cancelled|done", note:""}
    Atualiza uma aula (lesson).
    """
    try:
        lesson = Lesson.objects.select_related('student', 'student__user__profile').filter(id=event_id).first()
        if not lesson:
            return Response(
                {'error': 'Aula não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        # Verificar permissão (admin ou professor principal pode editar suas e dos parceiros; parceiro só se ainda vinculado)
        try:
            is_admin = request.user.profile.is_admin
            user_profile = request.user.profile.user_profile
            if is_admin:
                pass
            elif user_profile == UserProfile.PROFILE_TEACHER:
                # Prof. dono pode editar qualquer aula dos seus alunos (mantém histórico)
                if lesson.student.user_id != request.user.id:
                    return Response(
                        {'error': 'Sem permissão para editar esta aula'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            elif user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                if lesson.student.assigned_teacher_id != request.user.id or not lesson.student.user.profile.partner_teachers.filter(user=request.user).exists():
                    return Response(
                        {'error': 'Sem permissão para editar esta aula'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            else:
                if lesson.user_id != request.user.id:
                    return Response(
                        {'error': 'Sem permissão para editar esta aula'},
                        status=status.HTTP_403_FORBIDDEN
                    )
        except UserProfile.DoesNotExist:
            if lesson.user_id != request.user.id:
                return Response(
                    {'error': 'Sem permissão para editar esta aula'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Atualizar campos se fornecidos
        date_str = request.data.get('date')
        time_str = request.data.get('time')
        student_id = request.data.get('student_id')
        status_val = request.data.get('status')
        note = request.data.get('note')
        
        if date_str:
            lesson.date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        if time_str is not None:
            if time_str:
                try:
                    lesson.time = datetime.strptime(time_str, '%H:%M').time()
                except ValueError:
                    return Response(
                        {'error': 'Formato de horário inválido (use HH:MM)'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                lesson.time = None
        
        if student_id:
            try:
                # Professor dono: aluno deve ser dele; parceiro: aluno do dono que o tem vinculado
                try:
                    is_partner = request.user.profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
                except UserProfile.DoesNotExist:
                    is_partner = False
                if is_partner:
                    student = Student.objects.select_related('user__profile').get(id=student_id)
                    if student.assigned_teacher_id != request.user.id or not student.user.profile.partner_teachers.filter(user=request.user).exists():
                        return Response(
                            {'error': 'Aluno não encontrado'},
                            status=status.HTTP_404_NOT_FOUND
                        )
                else:
                    student = Student.objects.get(id=student_id, user=request.user)
                lesson.student = student
            except Student.DoesNotExist:
                return Response(
                    {'error': 'Aluno não encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        if status_val:
            # Mapear status
            if status_val == "done":
                lesson.realized = True
                # Manter status original
            else:
                lesson.realized = False
                status_map = {
                    "confirmed": "confirmed",
                    "pending": "pending",
                    "cancelled": "canceled",
                }
                lesson.status = status_map.get(status_val, "pending")
        
        if note is not None:
            lesson.info = note
        
        lesson.save()
        
        # Retornar evento atualizado
        time_str_resp = lesson.time.strftime('%H:%M') if lesson.time else ""
        final_status = "done" if lesson.realized else lesson.status
        status_map_back = {
            "confirmed": "confirmed",
            "pending": "pending",
            "canceled": "cancelled",
        }
        if final_status == "done":
            response_status = "done"
        else:
            response_status = status_map_back.get(final_status, "pending")
        
        return Response({
            'id': lesson.id,
            'date': lesson.date.strftime('%Y-%m-%d'),
            'time': time_str_resp,
            'student': lesson.student.name,
            'student_id': lesson.student.id,
            'status': response_status,
            'realized': lesson.realized,
            'note': lesson.info or ""
        })
    
    except ValueError as e:
        return Response(
            {'error': f'Formato de data inválido: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Erro ao atualizar aula: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def calendar_day_note(request):
    """
    GET /api/calendar/day-note/?date=YYYY-MM-DD
    Retorna a nota do dia para a data especificada.
    """
    try:
        date_str = request.query_params.get('date')
        if not date_str:
            return Response(
                {'error': 'Parâmetro date é obrigatório (formato: YYYY-MM-DD)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        note_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        try:
            day_note = DayNote.objects.get(user=request.user, date=note_date)
            return Response({
                'date': day_note.date.strftime('%Y-%m-%d'),
                'text': day_note.text
            })
        except DayNote.DoesNotExist:
            return Response({
                'date': date_str,
                'text': ''
            })
    
    except ValueError as e:
        return Response(
            {'error': f'Formato de data inválido: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Erro ao buscar nota: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def calendar_day_note_update(request):
    """
    PUT /api/calendar/day-note/
    Body: {date:"YYYY-MM-DD", text:"..."}
    Cria ou atualiza a nota do dia.
    """
    try:
        date_str = request.data.get('date')
        text = request.data.get('text', '')
        
        if not date_str:
            return Response(
                {'error': 'Campo date é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        note_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        day_note, created = DayNote.objects.update_or_create(
            user=request.user,
            date=note_date,
            defaults={'text': text}
        )
        
        return Response({
            'date': day_note.date.strftime('%Y-%m-%d'),
            'text': day_note.text
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
    except ValueError as e:
        return Response(
            {'error': f'Formato de data inválido: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Erro ao salvar nota: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class CalendarNewView(TemplateView):
    """View para renderizar o novo calendário"""
    template_name = "calendar_new.html"
    login_required = True

    def dispatch(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        if not request.user.is_authenticated:
            return redirect("login")
        if not _user_has_active_subscription(request.user):
            return redirect("planos")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            profile = self.request.user.profile
            context['user_is_admin'] = profile.is_admin
            context['is_partner_teacher'] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
            context['can_use_public_calendar'] = _user_can_use_public_calendar(self.request.user)
            context['slug_publico'] = getattr(profile, 'slug_publico', None) or ''
            context['agenda_publica_ativa'] = getattr(profile, 'agenda_publica_ativa', False)
            slug = getattr(profile, 'slug_publico', None)
            context['public_booking_url'] = self.request.build_absolute_uri(
                reverse('public-calendar-slug', kwargs={'slug': slug})
            ) if slug else ''
            context['public_availability'] = getattr(profile, 'public_availability', None) or {}
            context['public_booking_duration'] = getattr(profile, 'public_booking_duration', None) or 60
            # Professores que o dono da conta pode atribuir ao agendar aula (ele + parceiros)
            if profile.user_profile == UserProfile.PROFILE_TEACHER:
                partners = list(profile.partner_teachers.select_related('user').all())
                context['assignable_teachers'] = [
                    {'id': self.request.user.id, 'name': self.request.user.get_full_name() or self.request.user.username}
                ] + [{'id': p.user.id, 'name': p.user.get_full_name() or p.user.username} for p in partners]
            else:
                context['assignable_teachers'] = []
        except UserProfile.DoesNotExist:
            context['user_is_admin'] = False
            context['is_partner_teacher'] = False
            context['can_use_public_calendar'] = False
            context['assignable_teachers'] = []
        return context


def _user_can_use_public_calendar(user):
    """
    Agenda pública disponível para:
    - Admin, subscription_exempt
    - Trial (7 dias sem cartão) - tudo liberado durante trial
    - Assinatura Premium ou Platinum ativa
    """
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return True
    try:
        profile = user.profile
        if profile.is_admin or getattr(profile, 'subscription_exempt', False):
            return True
        if _user_is_in_trial(user):
            return True
        try:
            sub = user.subscription
            if sub.is_active and sub.tier in (Subscription.TIER_PREMIUM, Subscription.TIER_PLATINUM):
                return True
        except Subscription.DoesNotExist:
            pass
    except UserProfile.DoesNotExist:
        pass
    return False


def _get_teacher_for_public_booking(slug):
    """
    Resolve professor pelo slug para agenda pública.
    Retorna (teacher, error_msg).
    teacher é None se agenda indisponível ou slug inválido.
    Agenda pública disponível apenas para Premium+, admin ou subscription_exempt.
    """
    if not slug or not str(slug).strip():
        return (None, "Link inválido")
    slug = str(slug).strip().lower()
    try:
        profile = UserProfile.objects.select_related('user').get(slug_publico=slug)
    except UserProfile.DoesNotExist:
        return (None, "Agenda não encontrada")
    if not profile.agenda_publica_ativa:
        return (None, "Agenda indisponível")
    if not _user_can_use_public_calendar(profile.user):
        return (None, "Agenda indisponível")
    return (profile.user, None)


class PublicCalendarView(TemplateView):
    """Página pública de agendamento por professor (link único por slug)"""
    template_name = "public_calendar.html"

    def get(self, request, slug=None, *args, **kwargs):
        slug = slug or kwargs.get('slug', '')
        teacher, error = _get_teacher_for_public_booking(slug)
        teacher_whatsapp = ''
        if teacher and hasattr(teacher, 'profile'):
            teacher_whatsapp = (teacher.profile.phone or '').strip()
        context = {
            'teacher': teacher,
            'error': error,
            'slug': slug,
            'teacher_whatsapp': teacher_whatsapp,
            'public_booking_url': reverse('public-calendar-slug', kwargs={'slug': slug}) if slug else request.build_absolute_uri('/agendar/')
        }
        return render(request, self.template_name, context)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_availability_api(request, slug):
    """
    GET /api/public/<slug>/availability/?month=2026-02
    Retorna disponibilidade do professor (horários por dia) e dados públicos.
    Não expõe alunos, eventos privados, etc.
    """
    teacher, error = _get_teacher_for_public_booking(slug)
    if error or not teacher:
        return Response({'error': error or 'Agenda indisponível'}, status=status.HTTP_404_NOT_FOUND)

    month_str = request.query_params.get('month')
    if not month_str:
        return Response({'error': 'Parâmetro month obrigatório (YYYY-MM)'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        year, month = map(int, month_str.split('-'))
        first = date(year, month, 1)
        last = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year + 1, 1, 1) - timedelta(days=1)
    except (ValueError, TypeError):
        return Response({'error': 'Formato inválido. Use YYYY-MM'}, status=status.HTTP_400_BAD_REQUEST)

    profile = teacher.profile
    availability = profile.public_availability or {}
    duration = profile.public_booking_duration or 60

    # Default: seg-sex 18:00-21:00 se não configurado (0=dom, 1=seg,...,6=sab)
    if not availability:
        availability = {str(i): ["18:00", "21:00"] for i in range(1, 6)}

    def build_slots_for_date(d):
        # Python weekday: 0=seg, 6=dom. Mapear para 0=dom, 1=seg,...,6=sab
        wd = (d.weekday() + 1) % 7
        win = availability.get(str(wd))
        if not win or len(win) < 2:
            return []
        start, end = win[0], win[1]
        sh, sm = map(int, start.split(':'))
        eh, em = map(int, end.split(':'))
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        slots = []
        while start_min + duration <= end_min:
            slots.append(f'{start_min//60:02d}:{start_min%60:02d}')
            start_min += duration
        return slots

    # Horários já ocupados: Lesson (aulas) + PublicBookingRequest confirmados/pendentes
    lessons_qs = Lesson.objects.filter(
        user=teacher,
        date__gte=first,
        date__lte=last,
        status__in=['confirmed', 'pending']
    ).exclude(realized=True)
    busy_lessons = {(l.date.strftime('%Y-%m-%d'), l.time.strftime('%H:%M') if l.time else '') for l in lessons_qs}

    bookings_qs = PublicBookingRequest.objects.filter(
        teacher=teacher,
        requested_date__gte=first,
        requested_date__lte=last,
        status__in=['pending', 'confirmed']
    )
    busy_bookings = {(b.requested_date.strftime('%Y-%m-%d'), b.requested_time.strftime('%H:%M')) for b in bookings_qs}

    busy = busy_lessons | busy_bookings

    days_data = {}
    d = first
    while d <= last:
        key = d.strftime('%Y-%m-%d')
        all_slots = build_slots_for_date(d)
        free_slots = [s for s in all_slots if (key, s) not in busy]
        days_data[key] = {
            'slots': [{'time': s, 'available': (key, s) not in busy} for s in all_slots],
            'free_count': len(free_slots)
        }
        d += timedelta(days=1)

    return Response({
        'teacher_name': teacher.get_full_name() or teacher.username,
        'duration_minutes': duration,
        'month': month_str,
        'days': days_data
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def public_reservation_create(request, slug):
    """
    POST /api/public/<slug>/reservations/
    Cria solicitação de agendamento público.
    """
    teacher, error = _get_teacher_for_public_booking(slug)
    if error or not teacher:
        return Response({'error': error or 'Agenda indisponível'}, status=status.HTTP_404_NOT_FOUND)

    data = request.data
    name = (data.get('name') or '').strip()
    whatsapp = (data.get('whatsapp') or '').strip()
    email = (data.get('email') or '').strip()
    req_date = data.get('date')  # YYYY-MM-DD
    req_time = data.get('time')  # HH:MM

    if not name or len(name) < 2:
        return Response({'error': 'Informe seu nome.'}, status=status.HTTP_400_BAD_REQUEST)
    if not whatsapp or len(whatsapp.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')) < 10:
        return Response({'error': 'Informe um WhatsApp válido.'}, status=status.HTTP_400_BAD_REQUEST)
    if not email or '@' not in email:
        return Response({'error': 'Informe um e-mail válido.'}, status=status.HTTP_400_BAD_REQUEST)
    if not req_date or not req_time:
        return Response({'error': 'Selecione data e horário.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from datetime import datetime as dt
        requested_date = datetime.strptime(req_date, '%Y-%m-%d').date()
        requested_time = datetime.strptime(req_time, '%H:%M').time()
    except (ValueError, TypeError):
        return Response({'error': 'Data ou horário inválidos.'}, status=status.HTTP_400_BAD_REQUEST)

    today = timezone.localdate()
    if requested_date < today:
        return Response({'error': 'Não é possível agendar em data passada. Selecione a partir de hoje.'}, status=status.HTTP_400_BAD_REQUEST)
    if requested_date == today:
        now = timezone.localtime()
        requested_dt = datetime.combine(requested_date, requested_time)
        now_dt = datetime.combine(today, now.time())
        if requested_dt <= now_dt:
            return Response({'error': 'Este horário já passou. Selecione um horário futuro.'}, status=status.HTTP_400_BAD_REQUEST)

    # Verificar se horário está disponível
    profile = teacher.profile
    availability = profile.public_availability or {}
    wd = (requested_date.weekday() + 1) % 7  # 0=dom, 1=seg,...,6=sab
    win = availability.get(str(wd))
    if not win:
        return Response({'error': 'Este dia não está disponível na agenda.'}, status=status.HTTP_400_BAD_REQUEST)

    # Verificar conflito com aulas existentes
    existing = Lesson.objects.filter(user=teacher, date=requested_date, time=requested_time, status__in=['confirmed', 'pending']).exclude(realized=True)
    if existing.exists():
        return Response({'error': 'Este horário já foi reservado.'}, status=status.HTTP_400_BAD_REQUEST)
    existing_booking = PublicBookingRequest.objects.filter(teacher=teacher, requested_date=requested_date, requested_time=requested_time, status__in=['pending', 'confirmed'])
    if existing_booking.exists():
        return Response({'error': 'Este horário já foi reservado.'}, status=status.HTTP_400_BAD_REQUEST)

    duration = profile.public_booking_duration or 60

    booking = PublicBookingRequest.objects.create(
        teacher=teacher,
        requested_date=requested_date,
        requested_time=requested_time,
        duration_minutes=duration,
        student_name=name,
        student_whatsapp=whatsapp,
        student_email=email,
        subject=(data.get('subject') or '').strip(),
        notes=(data.get('notes') or '').strip(),
        status='pending'
    )
    return Response({
        'success': True,
        'reservation_id': f'RSV-{booking.id}',
        'message': 'Solicitação enviada. O professor confirmará em breve.'
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def public_booking_confirm(request, booking_id):
    """
    POST /api/public/booking/<id>/confirm/
    Professor confirma a solicitação: cria Aluno + Aula e marca PublicBookingRequest como confirmada.
    """
    try:
        pbr = PublicBookingRequest.objects.get(id=booking_id, status=PublicBookingRequest.STATUS_PENDING)
    except PublicBookingRequest.DoesNotExist:
        return Response({'error': 'Solicitação não encontrada ou já processada.'}, status=status.HTTP_404_NOT_FOUND)

    if pbr.teacher_id != request.user.id:
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    # Criar ou vincular aluno - buscar por email primeiro
    student = Student.objects.filter(
        user=request.user,
        email__iexact=pbr.student_email
    ).first()

    if not student:
        student = Student.objects.create(
            user=request.user,
            name=pbr.student_name,
            email=pbr.student_email,
            phone=pbr.student_whatsapp or '',
            status=Student.STATUS_ACTIVE,
        )

    # Criar aula
    title = pbr.subject or f"Aula com {pbr.student_name}"
    lesson = Lesson.objects.create(
        student=student,
        user=request.user,
        date=pbr.requested_date,
        time=pbr.requested_time,
        title=title,
        info=pbr.notes or '',
        status='confirmed',
        realized=False,
    )

    pbr.status = PublicBookingRequest.STATUS_CONFIRMED
    pbr.save(update_fields=['status', 'updated_at'])

    return Response({
        'success': True,
        'lesson_id': lesson.id,
        'student_id': student.id,
        'message': 'Solicitação confirmada. Aula criada no calendário.'
    }, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def public_booking_reject(request, booking_id):
    """
    POST /api/public/booking/<id>/reject/
    Professor recusa a solicitação.
    """
    try:
        pbr = PublicBookingRequest.objects.get(id=booking_id, status=PublicBookingRequest.STATUS_PENDING)
    except PublicBookingRequest.DoesNotExist:
        return Response({'error': 'Solicitação não encontrada ou já processada.'}, status=status.HTTP_404_NOT_FOUND)

    if pbr.teacher_id != request.user.id:
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    pbr.status = PublicBookingRequest.STATUS_CANCELLED
    pbr.save(update_fields=['status', 'updated_at'])

    return Response({
        'success': True,
        'message': 'Solicitação recusada.'
    }, status=200)


class TicketsView(TemplateView):
    """View para renderizar a tela de tickets de suporte (apenas admin)"""
    template_name = "tickets.html"
    login_required = True

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect("login")
        # Verificar se é admin
        try:
            is_admin = request.user.profile.is_admin
        except UserProfile.DoesNotExist:
            is_admin = False
        if not is_admin:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Acesso negado. Apenas administradores podem acessar esta página.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            profile = self.request.user.profile
            context['user_is_admin'] = profile.is_admin
            context['is_partner_teacher'] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
        except UserProfile.DoesNotExist:
            context['user_is_admin'] = False
            context['is_partner_teacher'] = False
        return context


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def support_tickets_list(request):
    """
    GET /api/support/tickets/list/
    Lista todos os tickets de suporte (apenas admin).
    Query params: category, impact, email_sent, search
    """
    try:
        # Verificar se é admin
        try:
            is_admin = request.user.profile.is_admin
        except UserProfile.DoesNotExist:
            is_admin = False
        
        if not is_admin:
            return Response(
                {'error': 'Apenas administradores podem acessar esta página'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Buscar todos os tickets
        tickets = SupportTicket.objects.select_related('user').all().order_by('-created_at')
        
        # Filtros
        category = request.query_params.get('category')
        if category:
            tickets = tickets.filter(category=category)
        
        impact = request.query_params.get('impact')
        if impact:
            tickets = tickets.filter(impact=impact)
        
        email_sent = request.query_params.get('email_sent')
        if email_sent is not None:
            tickets = tickets.filter(email_sent=email_sent.lower() == 'true')

        status_filter = request.query_params.get('status')
        if status_filter in ('open', 'closed'):
            tickets = tickets.filter(status=status_filter)

        search = request.query_params.get('search')
        if search:
            tickets = tickets.filter(
                Q(ticket_id__icontains=search) |
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        # Serializar
        tickets_data = []
        for ticket in tickets:
            tickets_data.append({
                'id': ticket.id,
                'ticket_id': ticket.ticket_id,
                'user': {
                    'id': ticket.user.id,
                    'username': ticket.user.username,
                    'email': ticket.user.email,
                    'full_name': ticket.user.get_full_name() or ticket.user.username,
                },
                'category': ticket.category,
                'category_display': ticket.get_category_display(),
                'impact': ticket.impact,
                'impact_display': ticket.get_impact_display(),
                'title': ticket.title,
                'description': ticket.description,
                'page': ticket.page,
                'query': ticket.query,
                'url': ticket.url,
                'created_at_local': ticket.created_at_local,
                'timezone': ticket.timezone,
                'created_at': ticket.created_at.isoformat(),
                'email_sent': ticket.email_sent,
                'email_error': ticket.email_error,
                'status': ticket.status,
                'status_display': ticket.get_status_display(),
                'resolved_at': ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            })
        
        return Response({
            'count': len(tickets_data),
            'tickets': tickets_data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        import traceback
        print(f"Erro ao listar tickets: {str(e)}")
        print(traceback.format_exc())
        return Response(
            {'error': f'Erro ao listar tickets: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _check_ticket_admin(request):
    """Verifica se o usuário é admin. Retorna (is_admin, error_response)."""
    try:
        is_admin = request.user.profile.is_admin
    except UserProfile.DoesNotExist:
        is_admin = False
    if not is_admin:
        return False, Response(
            {'error': 'Apenas administradores podem gerenciar tickets'},
            status=status.HTTP_403_FORBIDDEN
        )
    return True, None


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def support_ticket_detail(request, pk):
    """
    PATCH /api/support/tickets/<id>/ - Atualiza status (status: open|closed)
    DELETE /api/support/tickets/<id>/ - Exclui o ticket
    """
    is_admin, err = _check_ticket_admin(request)
    if not is_admin:
        return err

    try:
        ticket = SupportTicket.objects.get(pk=pk)
    except SupportTicket.DoesNotExist:
        return Response({'error': 'Ticket não encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        ticket.delete()
        return Response({'message': 'Ticket excluído com sucesso'}, status=status.HTTP_200_OK)

    if request.method == 'PATCH':
        new_status = request.data.get('status')
        if new_status in (SupportTicket.STATUS_OPEN, SupportTicket.STATUS_CLOSED):
            ticket.status = new_status
            if new_status == SupportTicket.STATUS_CLOSED:
                from django.utils import timezone
                ticket.resolved_at = timezone.now()
            else:
                ticket.resolved_at = None
            ticket.save(update_fields=['status', 'resolved_at'])
        return Response({
            'id': ticket.id,
            'ticket_id': ticket.ticket_id,
            'status': ticket.status,
            'status_display': ticket.get_status_display(),
            'resolved_at': ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def support_ticket_create(request):
    """
    POST /api/support/tickets/
    Cria um ticket de suporte e envia email para o suporte.
    Body JSON: {category, impact, title, description, page, query, url, created_at_local, timezone, user: {id, name, email}}
    """
    try:
        # Validações
        category = request.data.get('category', '').strip()
        impact = request.data.get('impact', '').strip()
        title = request.data.get('title', '').strip()
        description = request.data.get('description', '').strip()
        
        # Allowlists
        ALLOWED_CATEGORIES = ['bug', 'ux', 'payment', 'feature', 'other']
        ALLOWED_IMPACTS = ['low', 'medium', 'high']
        
        # Validações de tamanho e valores permitidos
        if not title or len(title) > 80:
            return Response(
                {'error': 'Título é obrigatório e deve ter no máximo 80 caracteres'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not description or len(description) > 2000:
            return Response(
                {'error': 'Descrição é obrigatória e deve ter no máximo 2000 caracteres'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if category not in ALLOWED_CATEGORIES:
            return Response(
                {'error': f'Categoria inválida. Permitidas: {", ".join(ALLOWED_CATEGORIES)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if impact not in ALLOWED_IMPACTS:
            return Response(
                {'error': f'Impacto inválido. Permitidos: {", ".join(ALLOWED_IMPACTS)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Dados do usuário (usar dados do request.user, não confiar no payload)
        user = request.user
        user_data = {
            'id': user.id,
            'name': user.get_full_name() or user.username,
            'email': user.email or '',
        }
        
        # Dados do contexto
        page = request.data.get('page', '')
        query = request.data.get('query', '')
        url = request.data.get('url', '')
        created_at_local = request.data.get('created_at_local', '')
        timezone_str = request.data.get('timezone', '')
        
        # Gerar ticket_id (UUID curto)
        ticket_id = str(uuid.uuid4())[:8].upper()
        
        # Timestamp server-side (timezone aware)
        server_timestamp = timezone.now()
        
        # Salvar ticket no banco de dados
        ticket = SupportTicket.objects.create(
            ticket_id=ticket_id,
            user=user,
            category=category,
            impact=impact,
            title=title,
            description=description,
            page=page,
            query=query,
            url=url,
            created_at_local=created_at_local,
            timezone=timezone_str,
            email_sent=False,
        )
        
        # Enviar email para o mesmo destino do formulário de contato (educaflowone@gmail.com)
        support_email = getattr(settings, 'SUPPORT_EMAIL', None) or getattr(settings, 'CONTACT_EMAIL', 'educaflowone@gmail.com')
        
        # Mapear categorias e impactos para labels
        category_labels = {
            'bug': 'Bug / Erro',
            'ux': 'UX / Layout',
            'payment': 'Pagamento / Assinatura',
            'feature': 'Sugestão',
            'other': 'Outro'
        }
        impact_labels = {
            'low': 'Baixo (incômodo)',
            'medium': 'Médio (atrapalha)',
            'high': 'Alto (bloqueia uso)'
        }
        
        subject = f'[Ticket #{ticket_id}] {title}'
        
        message = f"""
Novo ticket de suporte recebido:

Ticket ID: {ticket_id}
Data/Hora (servidor): {server_timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')}
Data/Hora (cliente): {created_at_local} (Timezone: {timezone_str})

Usuário:
- ID: {user_data['id']}
- Nome: {user_data['name']}
- Email: {user_data['email']}

Contexto:
- Página: {page}
- Query: {query}
- URL completa: {url}

Categoria: {category_labels.get(category, category)}
Impacto: {impact_labels.get(impact, impact)}

Título: {title}

Descrição:
{description}

---
Este é um email automático do sistema EDUCAflowOne.
"""
        
        # Tentar enviar email (não falha o endpoint se der erro)
        # IMPORTANTE: Usar fail_silently=True para evitar que timeout de email cause erro 500
        email_sent = False
        email_error_msg = ""
        print(f"\n{'='*60}")
        print(f"📧 TENTANDO ENVIAR EMAIL DE SUPORTE")
        print(f"{'='*60}")
        print(f"Ticket ID: {ticket_id}")
        print(f"Para: {support_email}")
        print(f"De: {settings.DEFAULT_FROM_EMAIL}")
        print(f"Assunto: {subject}")
        print(f"Backend: {settings.EMAIL_BACKEND}")
        print(f"Host: {getattr(settings, 'EMAIL_HOST', 'N/A')}:{getattr(settings, 'EMAIL_PORT', 'N/A')}")
        print(f"{'='*60}\n")
        
        # IMPORTANTE: fail_silently=True garante que falhas de email nunca bloqueiem o sistema.
        try:
            result = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[support_email],
                fail_silently=True,
            )
            if result:
                email_sent = True
                # Atualizar ticket com sucesso do email
                ticket.email_sent = True
                ticket.save(update_fields=['email_sent', 'email_error'])
                print(f"✅ Email enviado com sucesso para {support_email} (Ticket #{ticket_id})")
                print(f"   Verifique a caixa de entrada e spam do email: {support_email}\n")
            else:
                # send_mail retornou False (não deveria acontecer com fail_silently=False)
                email_error_msg = "Email backend retornou False (erro desconhecido)"
                ticket.email_sent = False
                ticket.email_error = email_error_msg[:500]
                ticket.save(update_fields=['email_sent', 'email_error'])
                print(f"⚠️  Email NÃO foi enviado (backend retornou False)")
                print(f"   Ticket #{ticket_id} foi salvo no banco de dados.\n")
        except Exception as email_error:
            # Capturar o erro real (timeout, autenticação, etc.)
            import traceback
            error_msg = str(email_error)
            email_error_msg = error_msg
            error_traceback = traceback.format_exc()
            
            # Verificar se é timeout
            is_timeout = 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower()
            
            ticket.email_sent = False
            ticket.email_error = email_error_msg[:500]  # Limitar tamanho
            ticket.save(update_fields=['email_sent', 'email_error'])
            
            print(f"\n{'='*60}")
            print(f"⚠️  ERRO AO ENVIAR EMAIL DE SUPORTE")
            print(f"{'='*60}")
            print(f"Ticket ID: {ticket_id}")
            print(f"Erro: {error_msg}")
            if is_timeout:
                print(f"⚠️  TIMEOUT detectado - verifique conectividade SMTP no Railway")
            print(f"\nTraceback completo:")
            print(error_traceback)
            print(f"\nConfiguração atual:")
            print(f"  EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
            print(f"  EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', 'N/A')}")
            print(f"  EMAIL_PORT: {getattr(settings, 'EMAIL_PORT', 'N/A')}")
            print(f"  EMAIL_USE_TLS: {getattr(settings, 'EMAIL_USE_TLS', 'N/A')}")
            print(f"  EMAIL_TIMEOUT: {getattr(settings, 'EMAIL_TIMEOUT', 'N/A')}")
            print(f"  EMAIL_HOST_USER: {getattr(settings, 'EMAIL_HOST_USER', 'N/A')}")
            print(f"  EMAIL_HOST_PASSWORD: {'***' if getattr(settings, 'EMAIL_HOST_PASSWORD', '') else 'N/A'}")
            print(f"  DEFAULT_FROM_EMAIL: {getattr(settings, 'DEFAULT_FROM_EMAIL', 'N/A')}")
            print(f"  SUPPORT_EMAIL: {support_email}")
            print(f"{'='*60}\n")
            print(f"ℹ️  Ticket #{ticket_id} criado, mas email NÃO foi enviado.")
            print(f"   O ticket foi salvo no banco de dados e pode ser visualizado no Django Admin.")
            # Não re-raise a exceção - continuar e retornar sucesso para o ticket
        
        # SEMPRE retornar sucesso, mesmo se o email falhar
        # O ticket foi criado com sucesso no banco
        return Response({
            'ticket_id': ticket_id,
            'email_sent': email_sent,
            'message': 'Ticket criado com sucesso' + (' e email enviado' if email_sent else ' (email não enviado - verifique logs)')
        }, status=status.HTTP_201_CREATED)
    
    except ValueError as e:
        # Erro de validação
        return Response(
            {'error': f'Erro de validação: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        # Capturar TODOS os erros possíveis e retornar JSON válido
        import traceback
        error_traceback = traceback.format_exc()
        print(f"\n{'='*60}")
        print(f"❌ ERRO CRÍTICO AO CRIAR TICKET DE SUPORTE")
        print(f"{'='*60}")
        print(f"Erro: {str(e)}")
        print(f"\nTraceback completo:")
        print(error_traceback)
        print(f"{'='*60}\n")
        return Response(
            {'error': f'Erro ao criar ticket: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def landing_contact_view(request):
    """
    POST /api/landing/contact/
    Formulário de contato da landing page (visitantes não logados).
    Campos: name, contact (WhatsApp ou Email), message (dúvida).
    Envia email para CONTACT_EMAIL (educaflowone@gmail.com).
    """
    try:
        name = (request.data.get('name') or '').strip()
        contact = (request.data.get('contact') or '').strip()
        message = (request.data.get('message') or '').strip()

        if not name:
            return Response({'error': 'Nome é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
        if not contact:
            return Response({'error': 'WhatsApp ou Email é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
        if not message:
            return Response({'error': 'Dúvida é obrigatória.'}, status=status.HTTP_400_BAD_REQUEST)

        if len(name) > 100:
            return Response({'error': 'Nome deve ter no máximo 100 caracteres.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(contact) > 150:
            return Response({'error': 'Contato deve ter no máximo 150 caracteres.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(message) > 500:
            return Response({'error': 'Dúvida deve ter no máximo 500 caracteres.'}, status=status.HTTP_400_BAD_REQUEST)

        contact_email = getattr(settings, 'CONTACT_EMAIL', 'educaflowone@gmail.com')
        subject = f'[Landing] Contato: {name}'

        body = f"""Novo contato pela landing page EDUCAflowOne

Nome: {name}
WhatsApp ou Email: {contact}
Dúvida:
{message}

---
Enviado em: {timezone.now().strftime('%Y-%m-%d %H:%M')}"""
        email_sent = False
        try:
            n = send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[contact_email],
                fail_silently=True,
            )
            email_sent = n > 0
        except Exception as e:
            print(f"[Landing Contact] Erro ao enviar email: {e}")

        return Response({
            'success': True,
            'email_sent': email_sent,
            'message': 'Mensagem enviada com sucesso! Entraremos em contato em breve.' if email_sent else 'Mensagem recebida. Pode haver atraso no retorno.',
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {'error': f'Erro ao enviar mensagem: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ==============================================================
# ADMIN PANEL — Painel Interno de Gestão de Usuários
# ==============================================================

class AdminPanelView(TemplateView):
    """Página standalone do painel admin. Acesso restrito a is_admin=True."""
    template_name = "admin_panel.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            if not request.user.profile.is_admin:
                return redirect('home')
        except Exception:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['user_is_admin'] = True
        return ctx


def _classify_segment(profile, subscription, now):
    """Retorna o segmento de retenção de um usuário."""
    has_active_sub = (
        subscription is not None and
        subscription.status == Subscription.STATUS_ACTIVE
    )
    if has_active_sub:
        if subscription.cancel_at_period_end:
            return 'canceling'
        return 'subscriber'
    if subscription is not None and subscription.status in (
        Subscription.STATUS_PAST_DUE, Subscription.STATUS_UNPAID
    ):
        return 'past_due'

    days_since = (now - profile.created_at).total_seconds() / 86400

    trial_end = profile.trial_ends_at
    if trial_end:
        days_left = (trial_end - now).total_seconds() / 86400
        if days_left > 0:
            # Últimos 3 dias do trial: prioridade para retenção (KPI "Trial expirando")
            if days_left <= 3:
                return 'trial_expiring'
            # Primeira semana após cadastro: ainda "Novo" (alinha com KPI "Novos (7 dias)")
            if days_since <= 7:
                return 'new'
            return 'trial_active'
        return 'trial_expired'

    # Sem trial configurado: recém-cadastrado na janela de 7 dias
    if days_since <= 7:
        return 'new'
    return 'no_sub'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_panel_users_api(request):
    """
    Retorna todos os usuários com dados de perfil, assinatura e engajamento.
    Restrito a admin.
    """
    try:
        if not request.user.profile.is_admin:
            return Response({'detail': 'Forbidden'}, status=403)
    except Exception:
        return Response({'detail': 'Forbidden'}, status=403)

    now = timezone.now()

    # Busca todos os perfis com subscription e usuário
    profiles = (
        UserProfile.objects
        .select_related('user')
        .prefetch_related('user__subscription')
        .exclude(is_admin=True)
        .order_by('-created_at')
    )

    # Engajamento: contagem de alunos, aulas e lançamentos financeiros por usuário
    from django.db.models import Count, Max
    student_counts = dict(
        Student.objects.values('user_id')
        .annotate(cnt=Count('id'))
        .values_list('user_id', 'cnt')
    )
    lesson_stats = {
        row['user_id']: {'count': row['cnt'], 'last': row['last']}
        for row in Lesson.objects
        .values('user_id')
        .annotate(cnt=Count('id'), last=Max('date'))
    }
    financial_counts = dict(
        FinancialEntry.objects.values('user_id')
        .annotate(cnt=Count('id'))
        .values_list('user_id', 'cnt')
    )

    users = []
    for profile in profiles:
        user = profile.user
        try:
            sub = user.subscription
        except Exception:
            sub = None

        segment = _classify_segment(profile, sub, now)
        u_id = user.id

        sub_data = None
        if sub:
            sub_data = {
                'status': sub.status,
                'tier': sub.tier,
                'plan': sub.plan,
                'current_period_end': sub.current_period_end.isoformat() if sub.current_period_end else None,
                'cancel_at_period_end': sub.cancel_at_period_end,
            }

        eng = lesson_stats.get(u_id, {})
        last_lesson = eng.get('last')

        users.append({
            'id': u_id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'phone': profile.phone or '',
            'city': profile.city or '',
            'state': profile.state or '',
            'subscription_exempt': profile.subscription_exempt,
            'trial_ends_at': profile.trial_ends_at.isoformat() if profile.trial_ends_at else None,
            'trial_ending_email_sent_at': profile.trial_ending_email_sent_at.isoformat() if profile.trial_ending_email_sent_at else None,
            'admin_notes': profile.admin_notes or '',
            'last_contacted_at': profile.last_contacted_at.isoformat() if profile.last_contacted_at else None,
            'created_at': profile.created_at.isoformat(),
            'subscription': sub_data,
            'engagement': {
                'student_count': student_counts.get(u_id, 0),
                'lesson_count': eng.get('count', 0),
                'last_lesson_date': last_lesson.isoformat() if last_lesson else None,
                'financial_entry_count': financial_counts.get(u_id, 0),
            },
            'segment': segment,
            'email_logs': [],  # preenchido abaixo
        })

    # Busca logs de email em batch para evitar N+1
    from .models import RetentionEmailLog
    user_ids = [u['id'] for u in users]
    logs_qs = RetentionEmailLog.objects.filter(user_id__in=user_ids).values(
        'user_id', 'email_type', 'sent_at', 'subject'
    )
    from collections import defaultdict
    logs_by_user = defaultdict(list)
    for log in logs_qs:
        logs_by_user[log['user_id']].append({
            'email_type': log['email_type'],
            'sent_at': log['sent_at'].isoformat(),
            'subject': log['subject'],
        })

    for u in users:
        u['email_logs'] = logs_by_user.get(u['id'], [])

    return Response({'users': users, 'generated_at': now.isoformat()})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def admin_panel_user_update(request, user_id):
    """
    Atualiza campos de gestão de um usuário pelo admin.
    Campos aceitos: trial_ends_at, subscription_exempt, admin_notes, last_contacted_at
    """
    try:
        if not request.user.profile.is_admin:
            return Response({'detail': 'Forbidden'}, status=403)
    except Exception:
        return Response({'detail': 'Forbidden'}, status=403)

    try:
        profile = UserProfile.objects.select_related('user').get(user_id=user_id)
    except UserProfile.DoesNotExist:
        return Response({'detail': 'Usuário não encontrado'}, status=404)

    data = request.data
    update_fields = []

    if 'trial_ends_at' in data:
        val = data['trial_ends_at']
        if val:
            from django.utils.dateparse import parse_datetime
            parsed = parse_datetime(val)
            if not parsed:
                # Tenta apenas data, adiciona fim do dia
                from django.utils.dateparse import parse_date
                d = parse_date(val)
                if d:
                    parsed = timezone.make_aware(
                        timezone.datetime(d.year, d.month, d.day, 23, 59, 59)
                    )
            profile.trial_ends_at = parsed
        else:
            profile.trial_ends_at = None
        update_fields.append('trial_ends_at')

    if 'subscription_exempt' in data:
        profile.subscription_exempt = bool(data['subscription_exempt'])
        update_fields.append('subscription_exempt')

    if 'admin_notes' in data:
        profile.admin_notes = str(data['admin_notes'])
        update_fields.append('admin_notes')

    if 'mark_contacted' in data and data['mark_contacted']:
        profile.last_contacted_at = timezone.now()
        update_fields.append('last_contacted_at')

    if update_fields:
        update_fields.append('updated_at')
        profile.save(update_fields=update_fields)

    return Response({
        'success': True,
        'user_id': user_id,
        'updated_fields': update_fields,
    })


# ── Admin: E-mails de Retenção ────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_email_preview(request):
    """
    Retorna assunto e HTML (com placeholder __PERSONAL_NOTE__) para preview.
    Query params: user_id, email_type
    """
    try:
        if not request.user.profile.is_admin:
            return Response({'detail': 'Forbidden'}, status=403)
    except Exception:
        return Response({'detail': 'Forbidden'}, status=403)

    user_id    = request.query_params.get('user_id')
    email_type = request.query_params.get('email_type')

    from .retention_emails import get_retention_email, EMAIL_TYPE_META
    if email_type not in EMAIL_TYPE_META:
        return Response({'detail': 'Tipo inválido'}, status=400)

    try:
        target_user = User.objects.get(id=user_id)
    except (User.DoesNotExist, ValueError):
        return Response({'detail': 'Usuário não encontrado'}, status=404)

    try:
        sub = target_user.subscription
    except Exception:
        sub = None

    subject, html = get_retention_email(email_type, target_user, sub)

    return Response({
        'subject': subject,
        'html': html,
        'meta': EMAIL_TYPE_META[email_type],
        'user_email': target_user.email,
        'user_name': (target_user.first_name or target_user.username).strip(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_send_retention_email(request):
    """
    Envia e-mail de retenção para um usuário específico.
    Body: { user_id, email_type, subject, personal_note }
    """
    try:
        if not request.user.profile.is_admin:
            return Response({'detail': 'Forbidden'}, status=403)
    except Exception:
        return Response({'detail': 'Forbidden'}, status=403)

    from .retention_emails import get_retention_email, render_final_email, EMAIL_TYPE_META
    from django.core.mail import EmailMessage as DjangoEmailMessage

    user_id       = request.data.get('user_id')
    email_type    = request.data.get('email_type', '')
    subject       = request.data.get('subject', '').strip()
    personal_note = request.data.get('personal_note', '').strip()

    if email_type not in EMAIL_TYPE_META:
        return Response({'detail': 'Tipo inválido'}, status=400)
    if not subject:
        return Response({'detail': 'Assunto obrigatório'}, status=400)

    try:
        target_user = User.objects.select_related('profile').get(id=user_id)
    except (User.DoesNotExist, ValueError):
        return Response({'detail': 'Usuário não encontrado'}, status=404)

    if not target_user.email:
        return Response({'detail': 'Usuário sem e-mail cadastrado'}, status=400)

    try:
        sub = target_user.subscription
    except Exception:
        sub = None

    _, html_with_placeholder = get_retention_email(email_type, target_user, sub)
    accent_color = EMAIL_TYPE_META[email_type]['color']
    final_html   = render_final_email(html_with_placeholder, personal_note, accent_color)

    try:
        msg = DjangoEmailMessage(
            subject=subject,
            body=final_html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[target_user.email],
        )
        msg.content_subtype = 'html'
        msg.send(fail_silently=False)
    except Exception as e:
        return Response({'detail': f'Erro ao enviar: {str(e)}'}, status=500)

    # Registra o envio no perfil (compat. legado), marca contato automático e no log histórico
    sent_at_now = timezone.now()
    last_contacted_iso = None
    try:
        profile = target_user.profile
        profile.last_retention_email_sent_at = sent_at_now
        profile.last_retention_email_type    = email_type
        profile.last_contacted_at = sent_at_now
        profile.save(
            update_fields=[
                'last_retention_email_sent_at',
                'last_retention_email_type',
                'last_contacted_at',
                'updated_at',
            ]
        )
        last_contacted_iso = profile.last_contacted_at.isoformat()
    except Exception:
        pass

    from .models import RetentionEmailLog
    log_entry = RetentionEmailLog.objects.create(
        user=target_user,
        email_type=email_type,
        subject=subject,
        personal_note=personal_note,
        sent_by=request.user,
    )

    return Response({
        'success': True,
        'sent_to': target_user.email,
        'email_type': email_type,
        'last_contacted_at': last_contacted_iso,
        'log': {
            'email_type': log_entry.email_type,
            'sent_at': log_entry.sent_at.isoformat(),
            'subject': log_entry.subject,
        },
    })
