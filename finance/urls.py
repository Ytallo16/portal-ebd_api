from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OfferingViewSet, offering_summary

router = DefaultRouter()
router.register('offerings', OfferingViewSet, basename='offerings')

urlpatterns = [
    path('', include(router.urls)),
    path('offerings-summary', offering_summary),
]
