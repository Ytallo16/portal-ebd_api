from rest_framework import serializers

from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.nome', read_only=True)

    class Meta:
        model = ActivityLog
        fields = [
            'id',
            'organization',
            'organization_name',
            'actor_name',
            'actor_email',
            'action',
            'resource',
            'object_reference',
            'event_type',
            'model_label',
            'changes',
            'method',
            'path',
            'status_code',
            'succeeded',
            'ip_address',
            'user_agent',
            'created_at',
        ]
