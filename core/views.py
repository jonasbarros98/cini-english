from datetime import datetime, date, timedelta
from django.utils import timezone
from django.db.models import Q, Sum, Count
from decimal import Decimal
from django.conf import settings
from django.urls import reverse
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse
from django.views.generic import TemplateView
from django.core.mail import send_mail
from django.template.loader import render_to_string
import stripe
import json
import os
import uuid
import threading
from .models import Invoice, FinancialEntry, UserProfile, LessonPlan, LessonPlanAttachment, BillingLog
from .models import Student, Lesson, Task, Subscription, StripeEvent, DayNote, SupportTicket
from .serializers import StudentSerializer, LessonSerializer, TaskSerializer
from .serializers import InvoiceSerializer, FinancialEntrySerializer, UserSerializer, LessonPlanSerializer, LessonPlanAttachmentSerializer, BillingLogSerializer, ProfileSerializer

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related("user", "assigned_teacher").all().order_by("name")
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # Suporta FormData e JSON
    
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
            # Prof. Parceiro: apenas alunos cujo dono ainda o tem em partner_teachers (acesso cortado ao desvincular)
            qs = qs.filter(user__profile__partner_teachers=self.request.user.profile)
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
        # assigned_teacher pode vir em validated_data; validar que é parceiro do dono
        user = self.request.user
        serializer.save(user=user)
    
    def perform_update(self, serializer):
        if self._is_partner_teacher():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Apenas o professor dono da conta pode editar alunos.")
        instance = self.get_object()
        if instance.user_id != self.request.user.id:
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
        partial = kwargs.get('partial', False)
        instance = self.get_object()
        if instance.user_id != request.user.id:
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
        if instance.user_id != request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Você não pode excluir este aluno.")
        return super().destroy(request, *args, **kwargs)


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
                    # Parceiro só vê aulas de alunos cujo dono ainda o tem em partner_teachers (acesso cortado ao desvincular)
                    qs = qs.filter(student__user__profile__partner_teachers=self.request.user.profile)
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

class AlunosView(TemplateView):
    """View para renderizar a página de alunos"""
    template_name = "alunos_new.html"
    
    def dispatch(self, request, *args, **kwargs):
        # Garantir que o usuário está autenticado
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect('/login/')
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


class DashboardView(TemplateView):
    """View para rota raiz - renderiza index.html se houver parâmetro view, senão redireciona para dashboard"""
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
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect('login')
        
        # Se houver parâmetro view na URL, renderizar index.html (para view-tasks, view-finance, etc)
        view_param = request.GET.get('view')
        if view_param:
            return super().dispatch(request, *args, **kwargs)
        
        # Caso contrário: Prof. Parceiro vai para calendário; demais para dashboard
        from django.shortcuts import redirect
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
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect('login')
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
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect('login')
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
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect("login")
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
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect("login")
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
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.odt', '.ods', '.odp']
    
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
                    # Parceiro só pode anexar em planejamentos seus e se ainda estiver vinculado ao dono do aluno
                    if plan.user_id != request.user.id or not plan.student.user.profile.partner_teachers.filter(user=request.user).exists():
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
                {'error': f'Arquivo muito grande. Tamanho máximo: 10MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Criar anexo
        attachment = LessonPlanAttachment.objects.create(
            lesson_plan=plan,
            file=file,
            original_filename=original_filename,
            file_size=file.size
        )
        
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
                    if plan.user_id != request.user.id or not plan.student.user.profile.partner_teachers.filter(user=request.user).exists():
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


class FinancialEntryViewSet(viewsets.ModelViewSet):
    queryset = FinancialEntry.objects.select_related("student", "user", "beneficiary_user").all()
    serializer_class = FinancialEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Admin vê todos os financial entries
        try:
            is_admin = self.request.user.profile.is_admin
            user_profile = self.request.user.profile.user_profile
        except UserProfile.DoesNotExist:
            is_admin = False
            user_profile = None
        
        if not is_admin:
            if user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                # Parceiro só vê lançamentos de alunos cujo dono ainda o tem em partner_teachers (acesso cortado ao desvincular)
                qs = qs.filter(student__user__profile__partner_teachers=self.request.user.profile).filter(
                    Q(user=self.request.user) | Q(beneficiary_user=self.request.user)
                ).distinct()
            elif user_profile == UserProfile.PROFILE_TEACHER:
                # Prof. Principal vê todos os lançamentos dos seus alunos (mantém histórico: quanto pagou ao parceiro, etc., mesmo após desvincular)
                qs = qs.filter(student__user=self.request.user)
            else:
                # Usuário sem perfil definido vê apenas os seus
                qs = qs.filter(user=self.request.user)
        
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
        
        # Formata dados do aluno
        student_data = {
            'id': student.id,
            'name': student.name,
            'phone': student.phone or '',
            'email': student.email or '',
            'plan_name': student.plan_name or '',
            'status': student.status or 'active',
            'lessons_total': student.lessons_total,
            'lessons_done': student.lessons_done,
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
                    # Parceiro só vê planejamentos de alunos cujo dono ainda o tem em partner_teachers (acesso cortado ao desvincular)
                    queryset = queryset.filter(student__user__profile__partner_teachers=self.request.user.profile)
                else:
                    # Outros usuários veem apenas os seus
                    queryset = queryset.filter(user=self.request.user)
            except UserProfile.DoesNotExist:
                queryset = queryset.filter(user=self.request.user)
        
        student_id = self.request.query_params.get('student', None)
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        return queryset

    def perform_create(self, serializer):
        # Preenche automaticamente o usuário logado ao criar um lesson plan
        serializer.save(user=self.request.user)
    
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
    Params: period (today|next7|week|nextweek|month|custom),
            start_date, end_date (quando custom),
            student_id, status (all|incomplete|no_goals|no_materials|ok), q (busca).
    Retorna JSON: period_label, total, days[], students[].
    """
    from collections import defaultdict
    now = timezone.now()
    try:
        tz = timezone.get_current_timezone()
    except Exception:
        tz = timezone.get_default_timezone()
    tz_date = now.astimezone(tz).date()

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
            qs = qs.filter(student__user__profile__partner_teachers=request.user.profile)
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
            students_qs = students_qs.filter(user__profile__partner_teachers=request.user.profile)
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
                # Prof. Parceiro vê apenas logs de seus próprios lançamentos
                qs = qs.filter(financial_entry__beneficiary_user=user)
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
    """
    plan = request.data.get('plan')
    
    if plan not in [Subscription.PLAN_MONTHLY, Subscription.PLAN_SEMESTRAL, Subscription.PLAN_ANNUAL]:
        return Response(
            {'error': 'Plano inválido. Use: monthly, semestral ou annual'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Mapeamento de planos para price IDs do Stripe
    # IMPORTANTE: Configure estes IDs no seu painel do Stripe
    PLAN_PRICE_IDS = {
        Subscription.PLAN_MONTHLY: os.environ.get("STRIPE_PRICE_ID_MONTHLY", ""),
        Subscription.PLAN_SEMESTRAL: os.environ.get("STRIPE_PRICE_ID_SEMESTRAL", ""),
        Subscription.PLAN_ANNUAL: os.environ.get("STRIPE_PRICE_ID_ANNUAL", ""),
    }
    
    price_id = PLAN_PRICE_IDS.get(plan)
    if not price_id:
        return Response(
            {'error': 'Price ID não configurado para este plano'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # URLs de retorno
    base_url = request.build_absolute_uri('/')[:-1]  # Remove trailing slash
    success_url = f"{base_url}/payment-processing/?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/signup/?plan={plan}"
    
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
                    plan=plan,
                    status=Subscription.STATUS_PENDING,
                    stripe_customer_id=customer_id
                )
            else:
                subscription.stripe_customer_id = customer_id
                subscription.save()
        
        # Criar Checkout Session
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
                'plan': plan,
            },
            subscription_data={
                'metadata': {
                    'user_id': str(request.user.id),
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
                plan = determine_plan_from_price_id(price_id)
                
                subscription = Subscription(
                    user=user,
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
                    plan = determine_plan_from_price_id(price_id)
                    
                    # Verificar se já existe subscription para este usuário
                    try:
                        subscription = Subscription.objects.get(user=user)
                        subscription.stripe_subscription_id = subscription_id
                        subscription.stripe_customer_id = customer_id
                    except Subscription.DoesNotExist:
                        subscription = Subscription(
                            user=user,
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
                    plan = determine_plan_from_price_id(price_id)
                    
                    # Verificar se já existe subscription para este usuário
                    try:
                        subscription = Subscription.objects.get(user=user)
                        subscription.stripe_subscription_id = subscription_id
                        subscription.stripe_customer_id = customer_id
                    except Subscription.DoesNotExist:
                        subscription = Subscription(
                            user=user,
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
    """Processa falha de pagamento - suspende acesso"""
    subscription_id = invoice.get('subscription')
    
    if not subscription_id:
        return
    
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        subscription.status = Subscription.STATUS_PAST_DUE
        subscription.save()
    except Subscription.DoesNotExist:
        pass


def handle_subscription_deleted(subscription_obj):
    """Processa cancelamento de assinatura"""
    subscription_id = subscription_obj.get('id')
    
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        subscription.status = Subscription.STATUS_CANCELED
        subscription.stripe_subscription_id = None  # Limpar referência
        subscription.save()
    except Subscription.DoesNotExist:
        pass


def handle_subscription_updated(subscription_obj):
    """Processa atualização de assinatura"""
    subscription_id = subscription_obj.get('id')
    
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        
        # Atualizar período
        subscription.current_period_start = timezone.make_aware(
            datetime.fromtimestamp(subscription_obj.get('current_period_start', 0))
        )
        subscription.current_period_end = timezone.make_aware(
            datetime.fromtimestamp(subscription_obj.get('current_period_end', 0))
        )
        
        # Atualizar status baseado no status do Stripe
        stripe_status = subscription_obj.get('status', '')
        if stripe_status == 'active':
            subscription.status = Subscription.STATUS_ACTIVE
        elif stripe_status == 'past_due':
            subscription.status = Subscription.STATUS_PAST_DUE
        elif stripe_status == 'canceled' or stripe_status == 'unpaid':
            subscription.status = Subscription.STATUS_CANCELED
        
        subscription.cancel_at_period_end = subscription_obj.get('cancel_at_period_end', False)
        subscription.save()
        
    except Subscription.DoesNotExist:
        pass


def determine_plan_from_price_id(price_id):
    """Determina o plano a partir do price_id do Stripe"""
    monthly_id = os.environ.get("STRIPE_PRICE_ID_MONTHLY", "")
    semestral_id = os.environ.get("STRIPE_PRICE_ID_SEMESTRAL", "")
    annual_id = os.environ.get("STRIPE_PRICE_ID_ANNUAL", "")
    
    if price_id == monthly_id:
        return Subscription.PLAN_MONTHLY
    elif price_id == semestral_id:
        return Subscription.PLAN_SEMESTRAL
    elif price_id == annual_id:
        return Subscription.PLAN_ANNUAL
    
    # Default
    return Subscription.PLAN_MONTHLY


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_status(request):
    """Retorna o status da assinatura do usuário"""
    try:
        subscription = request.user.subscription
        return Response({
            'has_subscription': True,
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
            context['subscription'] = subscription
            context['has_subscription'] = True
            context['is_active'] = subscription.is_active
            
            # Formatar nome do plano
            plan_names = {
                'monthly': 'Plano Mensal',
                'semestral': 'Plano Semestral',
                'annual': 'Plano Anual'
            }
            context['plan_name'] = plan_names.get(subscription.plan, subscription.get_plan_display())
            
            # Formatar preço (buscar do Stripe se necessário)
            plan_prices = {
                'monthly': 'R$ 49,90',
                'semestral': 'R$ 269,00',
                'annual': 'R$ 479,00'
            }
            context['plan_price'] = plan_prices.get(subscription.plan, '—')
            
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
        
        # Criar perfil padrão
        UserProfile.objects.create(
            user=user,
            user_profile=UserProfile.PROFILE_TEACHER,
            is_admin=False
        )
        
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
        
        # Filtrar APENAS dados do usuário logado - sem correção automática
        # Se não houver dados, retornará zero/vazio
        
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
        
        # Financeiro - vencendo hoje
        # Filtrar por beneficiary_user_id OU user_id
        due_today_entries = FinancialEntry.objects.filter(
            Q(user_id__in=user_ids) | Q(beneficiary_user_id__in=user_ids),
            due_date=today,
            status__in=[FinancialEntry.STATUS_PENDING, FinancialEntry.STATUS_OVERDUE]
        )
        due_today_amount = due_today_entries.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Financeiro - em atraso
        # Filtrar por beneficiary_user_id OU user_id
        overdue_entries = FinancialEntry.objects.filter(
            Q(user_id__in=user_ids) | Q(beneficiary_user_id__in=user_ids),
            due_date__lt=today,
            status__in=[FinancialEntry.STATUS_PENDING, FinancialEntry.STATUS_OVERDUE]
        )
        overdue_amount = overdue_entries.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Financeiro - recebido no mês
        # IMPORTANTE: Filtrar APENAS por beneficiary_user_id (quem recebe) OU user_id (quem criou)
        # Mostrar SOMENTE dados do usuário logado - se não tiver, mostrar zero
        paid_month_entries = FinancialEntry.objects.filter(
            Q(user_id__in=user_ids) | Q(beneficiary_user_id__in=user_ids),
            payment_date__gte=current_month_start,
            payment_date__lte=today,
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
        # Filtrar por beneficiary_user_id OU user_id
        upcoming_entries = FinancialEntry.objects.filter(
            Q(user_id__in=user_ids) | Q(beneficiary_user_id__in=user_ids),
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
        
        # Pendente no mês - APENAS do mês atual
        # Filtrar APENAS por beneficiary_user_id OU user_id do usuário logado
        # Mostrar SOMENTE dados do usuário logado - se não tiver, mostrar zero
        pending_month_entries = FinancialEntry.objects.filter(
            Q(user_id__in=user_ids) | Q(beneficiary_user_id__in=user_ids),
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
        
        # Campos diretos do UserProfile - incluir apenas os que foram enviados
        profile_fields = ['cpf_cnpj', 'phone', 'cep', 'address', 'city', 'state', 'timezone', 'language']
        for field in profile_fields:
            if field in raw_data:
                serializer_data[field] = raw_data.get(field, '') or ''
        
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
                # Parceiro só vê aulas de alunos cujo dono ainda o tem em partner_teachers (acesso cortado ao desvincular)
                qs = qs.filter(student__user__profile__partner_teachers=request.user.profile)
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
                'note': lesson.info or ""
            })
        
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
                if not lesson.student.user.profile.partner_teachers.filter(user=request.user).exists():
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
    Cria uma nova aula (lesson). Apenas professor dono da conta pode criar; user_id opcional para atribuir a si ou a um parceiro.
    """
    try:
        # Prof. Parceiro não pode criar aulas
        try:
            if request.user.profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
                return Response(
                    {'error': 'Apenas o professor dono da conta pode agendar aulas.'},
                    status=status.HTTP_403_FORBIDDEN
                )
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
        teacher_user = request.user
        if user_id is not None:
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
        
        # Aluno: deve pertencer ao dono da conta ou a um parceiro (lista já usada em listagem)
        try:
            profile = request.user.profile
            if profile.user_profile == UserProfile.PROFILE_TEACHER:
                partner_ids = list(profile.partner_teachers.values_list('user_id', flat=True))
                partner_ids.append(request.user.id)
                student = Student.objects.get(id=student_id, user_id__in=partner_ids)
            else:
                student = Student.objects.get(id=student_id, user=request.user)
        except Student.DoesNotExist:
            return Response(
                {'error': 'Aluno não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except UserProfile.DoesNotExist:
            student = Student.objects.get(id=student_id, user=request.user)
        
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
                if not lesson.student.user.profile.partner_teachers.filter(user=request.user).exists():
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
                    if not student.user.profile.partner_teachers.filter(user=request.user).exists():
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
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect("login")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            profile = self.request.user.profile
            context['user_is_admin'] = profile.is_admin
            context['is_partner_teacher'] = profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
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
            context['assignable_teachers'] = []
        return context


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
        
        # Enviar email
        support_email = getattr(settings, 'SUPPORT_EMAIL', 'jonasbarros98@gmail.com')
        
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
        
        # Tentar com fail_silently=False primeiro para capturar o erro real
        # Se der timeout, capturamos a exceção e tratamos
        try:
            result = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[support_email],
                fail_silently=False,  # False para capturar o erro real
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