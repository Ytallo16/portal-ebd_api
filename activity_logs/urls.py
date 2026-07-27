from django.urls import path

from .views import ActivityLogListView


urlpatterns = [
    path('activity-logs/', ActivityLogListView.as_view(), name='activity-log-list'),
]

