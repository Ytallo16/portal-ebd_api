from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import UserViewSet, logout, me, update_context

router = DefaultRouter()
router.register('users', UserViewSet, basename='users')

urlpatterns = [
    path('', include(router.urls)),
    path('me', me, name='me'),
    path('me/context', update_context, name='me-context'),
    path('auth/logout', logout, name='logout'),
]
