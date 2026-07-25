from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import UserViewSet, change_password, logout, me, me_avatar, update_context

router = DefaultRouter()
router.register('users', UserViewSet, basename='users')

urlpatterns = [
    path('', include(router.urls)),
    path('me', me, name='me'),
    path('me/', me, name='me-trailing-slash'),
    path('me/context', update_context, name='me-context'),
    path('me/change-password', change_password, name='me-change-password'),
    path('me/avatar', me_avatar, name='me-avatar'),
    path('auth/logout', logout, name='logout'),
]
