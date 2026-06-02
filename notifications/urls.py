from django.urls import path

from .views import notification_list, notification_read, notification_read_all

urlpatterns = [
    path('notifications/', notification_list),
    path('notifications/read-all/', notification_read_all),
    path('notifications/<int:pk>/read/', notification_read),
]
