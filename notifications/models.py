from django.conf import settings
from django.db import models

from core.models import OrganizationScopedModel, TimeStampedModel

from .constants import KIND_CHOICES, SEVERITY_CHOICES, SEVERITY_INFO


class Notification(TimeStampedModel, OrganizationScopedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    kind = models.CharField(max_length=40, choices=KIND_CHOICES)
    dedupe_key = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default='')
    action_path = models.CharField(max_length=512)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_INFO)
    metadata = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'organization', 'dedupe_key'],
                name='uniq_notification_user_org_dedupe',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'organization', 'read_at']),
        ]

    def __str__(self):
        return f'{self.kind}: {self.title}'
