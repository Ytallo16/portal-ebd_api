from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from accounts.jwt_views import CookieTokenObtainPairView, CookieTokenRefreshView
from core.views import health

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/health/', health, name='health'),
    path('api/v1/auth/login', CookieTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/refresh', CookieTokenRefreshView.as_view(), name='token_refresh'),
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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
