from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ChurchViewSet, OrganizationMembershipViewSet, OrganizationViewSet

router = DefaultRouter()
# churches antes de organizations — senão o router trata "churches" como pk de Organization
router.register('organizations/churches', ChurchViewSet, basename='churches')
router.register('organizations', OrganizationViewSet, basename='organizations')
router.register('organization-memberships', OrganizationMembershipViewSet, basename='organization-memberships')

urlpatterns = [path('', include(router.urls))]
