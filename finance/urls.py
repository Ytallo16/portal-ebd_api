from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .resumo import finance_lancamentos, finance_resumo
from .views import OfferingViewSet, offering_summary

router = DefaultRouter()
router.register('offerings', OfferingViewSet, basename='offerings')

urlpatterns = [
    path('', include(router.urls)),
    path('offerings-summary', offering_summary),
    path('finance/resumo/', finance_resumo),
    path('finance/lancamentos/', finance_lancamentos),
]
