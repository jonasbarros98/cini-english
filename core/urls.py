from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.views.generic import TemplateView, RedirectView

from .views import (
    StudentViewSet, LessonViewSet, TaskViewSet, HomeView, DashboardView, DashboardHomeView,
    InvoiceViewSet, FinancialEntryViewSet, UserViewSet, LessonPlanViewSet, BillingLogViewSet,
    login_view, logout_view, current_user_view,
    create_checkout_session, stripe_webhook, subscription_status, subscription_sync, verify_checkout_session, signup_view,
    create_portal_session, upgrade_portal_session, PlanosView, dashboard_summary_view, PerfilView, TutorialView,
    profile_get_view, profile_update_view, profile_partner_teachers_lookup,
    profile_partner_teachers_create, profile_partner_teachers_remove,
    profile_partner_teachers_update,
    welcome_dismiss_view,
    PlanningListView, planning_list_api,
    planning_edit_redirect, planning_new_redirect,
    upload_planning_attachment, delete_planning_attachment,
    AlunosView, CalendarNewView, FinanceView, ReciboView, TicketsView,
    calendar_events, calendar_event_status, calendar_event_create, calendar_event_update,
    calendar_day_note, calendar_day_note_update,
    support_ticket_create, support_tickets_list, support_ticket_detail, landing_contact_view,
    PublicCalendarView, public_availability_api, public_reservation_create,
    public_booking_confirm, public_booking_reject,
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
    path("landing/", TemplateView.as_view(template_name="test_landing_v5.html"), name="landing"),
    path("landing-v3/", TemplateView.as_view(template_name="test_landing_v3.html"), name="landing-v3"),
    path("landing-v4/", TemplateView.as_view(template_name="test_landing_v4.html"), name="landing-v4"),
    path("landing-v5/", TemplateView.as_view(template_name="test_landing_v5.html"), name="landing-v5"),
    path("agendar/", PublicCalendarView.as_view(), name="public-calendar"),
    path("agendar/<slug:slug>/", PublicCalendarView.as_view(), name="public-calendar-slug"),
    path("api/public/<slug:slug>/availability/", public_availability_api, name="api-public-availability"),
    path("api/public/<slug:slug>/reservations/", public_reservation_create, name="api-public-reservations"),
    path("api/public/booking/<int:booking_id>/confirm/", public_booking_confirm, name="api-public-booking-confirm"),
    path("api/public/booking/<int:booking_id>/reject/", public_booking_reject, name="api-public-booking-reject"),
    path("dashboard/", DashboardHomeView.as_view(), name="dashboard-home"),
    path("perfil/", PerfilView.as_view(), name="perfil"),
    path("", HomeView.as_view(), name="home"),
    path("cobranca/", RedirectView.as_view(url="/?view=view-billing", permanent=False), name="cobranca"),
    path("alunos/", AlunosView.as_view(), name="alunos"),
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
    path("api/profile/partner-teachers/lookup/", profile_partner_teachers_lookup, name="profile-partner-teachers-lookup"),
    path("api/profile/partner-teachers/", profile_partner_teachers_create, name="profile-partner-teachers-create"),
    path("api/profile/partner-teachers/<int:user_id>/remove/", profile_partner_teachers_remove, name="profile-partner-teachers-remove"),
    path("api/profile/partner-teachers/<int:user_id>/", profile_partner_teachers_update, name="profile-partner-teachers-update"),
    path("api/profile/welcome-dismiss/", welcome_dismiss_view, name="welcome-dismiss"),
    path("api/dashboard/summary/", dashboard_summary_view, name="dashboard-summary"),
    path("api/subscription/create-checkout/", create_checkout_session, name="create-checkout"),
    path("api/subscription/status/", subscription_status, name="subscription-status"),
    path("api/subscription/sync/", subscription_sync, name="subscription-sync"),
    path("api/subscription/verify-session/", verify_checkout_session, name="verify-checkout-session"),
    path("api/subscription/create-portal/", create_portal_session, name="create-portal"),
    path("api/subscription/upgrade-portal/", upgrade_portal_session, name="upgrade-portal"),
    path("api/webhooks/stripe/", stripe_webhook, name="stripe-webhook"),
    path("planos/", PlanosView.as_view(), name="planos"),
    path("tutorial/", TutorialView.as_view(), name="tutorial"),
    path("planejamento/", PlanningListView.as_view(), name="planning-list"),
    path("planejamento/editar/", planning_edit_redirect, name="planning-edit"),
    path("planejamento/novo/", planning_new_redirect, name="planning-new"),
    path("api/planning/list/", planning_list_api, name="api-planning-list"),
    path("api/planning/<int:plan_id>/attachments/", upload_planning_attachment, name="api-planning-upload-attachment"),
    path("api/planning/attachments/<int:attachment_id>/", delete_planning_attachment, name="api-planning-delete-attachment"),
    # Calendar endpoints
    path("calendar/", CalendarNewView.as_view(), name="calendar-new"),
    path("financeiro/", FinanceView.as_view(), name="finance"),
    path("recibo/<int:entry_id>/", ReciboView.as_view(), name="recibo"),
    path("api/calendar/events/", calendar_events, name="api-calendar-events"),
    path("api/calendar/events/<int:event_id>/status/", calendar_event_status, name="api-calendar-event-status"),
    path("api/calendar/events/create/", calendar_event_create, name="api-calendar-event-create"),
    path("api/calendar/events/<int:event_id>/", calendar_event_update, name="api-calendar-event-update"),
    path("api/calendar/day-note/", calendar_day_note, name="api-calendar-day-note"),
    path("api/calendar/day-note/update/", calendar_day_note_update, name="api-calendar-day-note-update"),
    # Support ticket endpoints
    path("api/support/tickets/", support_ticket_create, name="api-support-tickets"),
    path("api/landing/contact/", landing_contact_view, name="api-landing-contact"),
    path("api/support/tickets/list/", support_tickets_list, name="api-support-tickets-list"),
    path("api/support/tickets/<int:pk>/", support_ticket_detail, name="api-support-ticket-detail"),
    # Tickets view (admin only)
    path("tickets/", TicketsView.as_view(), name="tickets"),
]
