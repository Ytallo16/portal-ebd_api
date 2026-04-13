from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AttendanceSheetViewSet, lesson_class_attendance

router = DefaultRouter()
router.register('attendance-sheets', AttendanceSheetViewSet, basename='attendance-sheets')

urlpatterns = [
    path('', include(router.urls)),
    path('lessons/<int:lesson_id>/classes/<int:class_id>/attendance', lesson_class_attendance),
]
