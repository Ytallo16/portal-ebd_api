from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    EVENT_CREATE = 'CREATE'
    EVENT_UPDATE = 'UPDATE'
    EVENT_DELETE = 'DELETE'
    EVENT_LOGIN = 'LOGIN'
    EVENT_REQUEST = 'REQUEST'
    EVENT_CHOICES = (
        (EVENT_CREATE, 'Criação'),
        (EVENT_UPDATE, 'Edição'),
        (EVENT_DELETE, 'Exclusão'),
        (EVENT_LOGIN, 'Acesso'),
        (EVENT_REQUEST, 'Operação'),
    )

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.PROTECT,
        related_name='activity_logs',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
    )
    actor_name = models.CharField(max_length=255)
    actor_email = models.EmailField(blank=True)
    action = models.CharField(max_length=255)
    resource = models.CharField(max_length=120)
    object_reference = models.CharField(max_length=120, blank=True)
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_CHOICES,
        default=EVENT_REQUEST,
    )
    model_label = models.CharField(max_length=150, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    status_code = models.PositiveSmallIntegerField()
    succeeded = models.BooleanField(default=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['organization', 'succeeded', '-created_at']),
            models.Index(fields=['actor', '-created_at']),
        ]

    def __str__(self):
        return f'{self.actor_name}: {self.action}'
