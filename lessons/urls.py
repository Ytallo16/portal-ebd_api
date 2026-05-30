from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LessonViewSet, TrimesterViewSet
from .schedule_views import LessonScheduleViewSet

router = DefaultRouter()
router.register('lessons', LessonViewSet, basename='lessons')
router.register('trimesters', TrimesterViewSet, basename='trimesters')
router.register('lesson-schedules', LessonScheduleViewSet, basename='lesson-schedules')

urlpatterns = [path('', include(router.urls))]
