from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.views import health

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/health/', health, name='health'),
    path('api/v1/auth/login', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/', include('accounts.urls')),
    path('api/v1/', include('organizations.urls')),
    path('api/v1/', include('access_control.urls')),
    path('api/v1/', include('classrooms.urls')),
    path('api/v1/', include('students.urls')),
    path('api/v1/', include('lessons.urls')),
    path('api/v1/', include('attendance.urls')),
    path('api/v1/', include('finance.urls')),
    path('api/v1/', include('publications.urls')),
    path('api/v1/', include('dashboard.urls')),
]
