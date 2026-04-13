from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PublicationControlViewSet

router = DefaultRouter()
router.register('publication-controls', PublicationControlViewSet, basename='publication-controls')

urlpatterns = [path('', include(router.urls))]
