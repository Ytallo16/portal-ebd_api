from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LessonViewSet, TrimesterViewSet
from .schedule_views import LessonScheduleViewSet
from .attachment_views import LessonAttachmentViewSet

router = DefaultRouter()
router.register('lessons', LessonViewSet, basename='lessons')
router.register('trimesters', TrimesterViewSet, basename='trimesters')
router.register('lesson-schedules', LessonScheduleViewSet, basename='lesson-schedules')
router.register('lesson-attachments', LessonAttachmentViewSet, basename='lesson-attachments')

urlpatterns = [path('', include(router.urls))]
