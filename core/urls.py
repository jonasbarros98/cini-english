from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import StudentViewSet, LessonViewSet, TaskViewSet, DashboardView, InvoiceViewSet

router = DefaultRouter()
router.register(r"students", StudentViewSet, basename="student")
router.register(r"lessons", LessonViewSet, basename="lesson")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"invoices", InvoiceViewSet, basename="invoice")

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("api/", include(router.urls)),
]
