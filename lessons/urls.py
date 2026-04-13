from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LessonViewSet, TrimesterViewSet

router = DefaultRouter()
router.register('lessons', LessonViewSet, basename='lessons')
router.register('trimesters', TrimesterViewSet, basename='trimesters')

urlpatterns = [path('', include(router.urls))]
