from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.views.generic import TemplateView

from .views import (
    StudentViewSet, LessonViewSet, TaskViewSet, DashboardView, DashboardHomeView,
    InvoiceViewSet, FinancialEntryViewSet, UserViewSet, LessonPlanViewSet, BillingLogViewSet,
    login_view, logout_view, current_user_view,
    create_checkout_session, stripe_webhook, subscription_status, signup_view,
    create_portal_session, PlanosView, dashboard_summary_view, PerfilView, TutorialView,
    profile_get_view, profile_update_view, welcome_dismiss_view,
    PlanningListView, planning_list_api,
    planning_edit_redirect, planning_new_redirect,
    upload_planning_attachment, delete_planning_attachment,
)

router = DefaultRouter()
router.register(r"students", StudentViewSet, basename="student")
router.register(r"lessons", LessonViewSet, basename="lesson")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"financial-entries", FinancialEntryViewSet, basename="financial-entry")
router.register(r"billing-logs", BillingLogViewSet, basename="billing-log")
router.register(r"users", UserViewSet, basename="user")
router.register(r"lesson-plans", LessonPlanViewSet, basename="lesson-plan")

urlpatterns = [
    path("landing/", TemplateView.as_view(template_name="landing.html"), name="landing"),
    path("dashboard/", DashboardHomeView.as_view(), name="dashboard-home"),
    path("perfil/", PerfilView.as_view(), name="perfil"),
    path("", DashboardView.as_view(), name="dashboard"),
    path("login/", TemplateView.as_view(template_name="login.html"), name="login"),
    path("signup/", TemplateView.as_view(template_name="signup.html"), name="signup"),
    path("payment-processing/", TemplateView.as_view(template_name="payment_processing.html"), name="payment-processing"),
    path("api/", include(router.urls)),
    path("api/auth/login/", login_view, name="api-login"),
    path("api/auth/logout/", logout_view, name="api-logout"),
    path("api/auth/signup/", signup_view, name="api-signup"),
    path("api/auth/current-user/", current_user_view, name="api-current-user"),
    path("api/profile/me/", profile_get_view, name="profile-get"),
    path("api/profile/update/", profile_update_view, name="profile-update"),
    path("api/profile/welcome-dismiss/", welcome_dismiss_view, name="welcome-dismiss"),
    path("api/dashboard/summary/", dashboard_summary_view, name="dashboard-summary"),
    path("api/subscription/create-checkout/", create_checkout_session, name="create-checkout"),
    path("api/subscription/status/", subscription_status, name="subscription-status"),
    path("api/subscription/create-portal/", create_portal_session, name="create-portal"),
    path("api/webhooks/stripe/", stripe_webhook, name="stripe-webhook"),
    path("planos/", PlanosView.as_view(), name="planos"),
    path("tutorial/", TutorialView.as_view(), name="tutorial"),
    path("planejamento/", PlanningListView.as_view(), name="planning-list"),
    path("planejamento/editar/", planning_edit_redirect, name="planning-edit"),
    path("planejamento/novo/", planning_new_redirect, name="planning-new"),
    path("api/planning/list/", planning_list_api, name="api-planning-list"),
    path("api/planning/<int:plan_id>/attachments/", upload_planning_attachment, name="api-planning-upload-attachment"),
    path("api/planning/attachments/<int:attachment_id>/", delete_planning_attachment, name="api-planning-delete-attachment"),
]
