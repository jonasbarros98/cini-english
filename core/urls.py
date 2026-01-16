from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.views.generic import TemplateView

from .views import (
    StudentViewSet, LessonViewSet, TaskViewSet, DashboardView, 
    InvoiceViewSet, FinancialEntryViewSet, UserViewSet, LessonPlanViewSet,
    login_view, logout_view, current_user_view
)

router = DefaultRouter()
router.register(r"students", StudentViewSet, basename="student")
router.register(r"lessons", LessonViewSet, basename="lesson")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"financial-entries", FinancialEntryViewSet, basename="financial-entry")
router.register(r"users", UserViewSet, basename="user")
router.register(r"lesson-plans", LessonPlanViewSet, basename="lesson-plan")

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("login/", TemplateView.as_view(template_name="login.html"), name="login"),
    path("api/", include(router.urls)),
    path("api/auth/login/", login_view, name="api-login"),
    path("api/auth/logout/", logout_view, name="api-logout"),
    path("api/auth/current-user/", current_user_view, name="api-current-user"),
]
