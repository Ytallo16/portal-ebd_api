from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ModulePermissionViewSet, RoleViewSet, UserRoleViewSet

router = DefaultRouter()
router.register('roles', RoleViewSet, basename='roles')
router.register('module-permissions', ModulePermissionViewSet, basename='module-permissions')
router.register('user-roles', UserRoleViewSet, basename='user-roles')

urlpatterns = [path('', include(router.urls))]
