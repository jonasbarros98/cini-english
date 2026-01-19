from datetime import datetime
from datetime import date
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import Invoice, FinancialEntry, UserProfile, LessonPlan, BillingLog
from .models import Student, Lesson, Task
from .serializers import StudentSerializer, LessonSerializer, TaskSerializer
from .serializers import InvoiceSerializer, FinancialEntrySerializer, UserSerializer, LessonPlanSerializer, BillingLogSerializer

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
    except UserProfile.DoesNotExist:
        is_admin = False
        user_profile = None
    
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_admin': is_admin,
        'user_profile': user_profile,
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