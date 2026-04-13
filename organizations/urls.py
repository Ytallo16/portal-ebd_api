from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OrganizationMembershipViewSet, OrganizationViewSet

router = DefaultRouter()
router.register('organizations', OrganizationViewSet, basename='organizations')
router.register('organization-memberships', OrganizationMembershipViewSet, basename='organization-memberships')

urlpatterns = [path('', include(router.urls))]
