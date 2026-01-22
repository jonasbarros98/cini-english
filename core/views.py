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
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse
from django.views.generic import TemplateView
import stripe
import json
import os
from .models import Invoice, FinancialEntry, UserProfile, LessonPlan, BillingLog
from .models import Student, Lesson, Task, Subscription, StripeEvent
from .serializers import StudentSerializer, LessonSerializer, TaskSerializer
from .serializers import InvoiceSerializer, FinancialEntrySerializer, UserSerializer, LessonPlanSerializer, BillingLogSerializer, ProfileSerializer

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related("user").all().order_by("name")
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # Admin vê todos os students, usuários normais veem apenas os seus
        try:
            is_admin = self.request.user.profile.is_admin
        except UserProfile.DoesNotExist:
            is_admin = False
        
        if not is_admin:
            try:
                user_profile = self.request.user.profile.user_profile
                if user_profile == UserProfile.PROFILE_TEACHER:
                    # Prof. Principal vê seus students + students dos parceiros vinculados
                    partner_ids = list(self.request.user.profile.partner_teachers.values_list('user_id', flat=True))
                    partner_ids.append(self.request.user.id)
                    qs = qs.filter(user_id__in=partner_ids)
                else:
                    # Outros usuários veem apenas os seus
                    qs = qs.filter(user=self.request.user)
            except UserProfile.DoesNotExist:
                qs = qs.filter(user=self.request.user)
        
        return qs
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        # Preenche automaticamente o usuário logado ao criar um student
        serializer.save(user=self.request.user)


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
                    # Prof. Principal vê suas lessons + lessons dos parceiros vinculados
                    partner_ids = list(self.request.user.profile.partner_teachers.values_list('user_id', flat=True))
                    partner_ids.append(self.request.user.id)
                    qs = qs.filter(user_id__in=partner_ids)
                else:
                    # Outros usuários veem apenas as suas
                    qs = qs.filter(user=self.request.user)
            except UserProfile.DoesNotExist:
                qs = qs.filter(user=self.request.user)

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

class DashboardView(TemplateView):
    template_name = "index.html"

class DashboardHomeView(TemplateView):
    template_name = "dashboard_home.html"
    login_required = True
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)

class PerfilView(TemplateView):
    template_name = "perfil_user.html"
    login_required = True
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)


class TutorialView(TemplateView):
    template_name = "tutorial.html"
    login_required = True

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect("login")
        return super().dispatch(request, *args, **kwargs)


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
    queryset = FinancialEntry.objects.select_related("student", "user").all()
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
                # Prof. Parceiro vê apenas lançamentos onde beneficiary_user = ele
                qs = qs.filter(beneficiary_user=self.request.user)
            elif user_profile == UserProfile.PROFILE_TEACHER:
                # Prof. Principal vê:
                # 1. Lançamentos criados por ele (user = ele)
                # 2. Lançamentos atribuídos a ele (beneficiary_user = ele)
                # 3. Lançamentos dos parceiros vinculados (user IN parceiros OU beneficiary_user IN parceiros)
                partner_ids = list(self.request.user.profile.partner_teachers.values_list('user_id', flat=True))
                qs = qs.filter(
                    Q(user=self.request.user) |
                    Q(beneficiary_user=self.request.user) |
                    Q(user_id__in=partner_ids) |
                    Q(beneficiary_user_id__in=partner_ids)
                ).distinct()
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
        # Preenche automaticamente o usuário logado ao criar um financial entry
        beneficiary_user = serializer.validated_data.get('beneficiary_user')
        if not beneficiary_user:
            # Se não especificado, o beneficiário é o próprio criador
            beneficiary_user = self.request.user
        serializer.save(user=self.request.user, beneficiary_user=beneficiary_user)
    
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

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """View para fazer login"""
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
                    # Prof. Principal vê seus lesson plans + lesson plans dos parceiros vinculados
                    partner_ids = list(self.request.user.profile.partner_teachers.values_list('user_id', flat=True))
                    partner_ids.append(self.request.user.id)
                    queryset = queryset.filter(user_id__in=partner_ids)
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
                'paid_month_amount': float(paid_month_amount)
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