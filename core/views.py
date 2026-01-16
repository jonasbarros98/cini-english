from datetime import datetime
from datetime import date
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import Invoice, FinancialEntry, UserProfile
from .models import Student, Lesson, Task
from .serializers import StudentSerializer, LessonSerializer, TaskSerializer
from .serializers import InvoiceSerializer, FinancialEntrySerializer, UserSerializer

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all().order_by("name")
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]


class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.select_related("student").all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

from django.views.generic import TemplateView

class DashboardView(TemplateView):
    template_name = "index.html"

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("student").all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
            except UserProfile.DoesNotExist:
                is_admin = False
            
            return Response({
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_admin': is_admin,
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
    except UserProfile.DoesNotExist:
        is_admin = False
    
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_admin': is_admin,
    })


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