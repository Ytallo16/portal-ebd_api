from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ClassGroupViewSet, ClassTeacherViewSet

router = DefaultRouter()
router.register('classes', ClassGroupViewSet, basename='classes')
router.register('class-teachers', ClassTeacherViewSet, basename='class-teachers')

urlpatterns = [path('', include(router.urls))]
