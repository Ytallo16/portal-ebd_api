from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'organization', 'kind', 'title', 'read_at', 'created_at')
    list_filter = ('kind', 'severity', 'organization')
    search_fields = ('title', 'dedupe_key', 'user__email')
