from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id',
            'kind',
            'title',
            'body',
            'action_path',
            'severity',
            'metadata',
            'read',
            'read_at',
            'created_at',
        ]
        read_only_fields = fields

    def get_read(self, obj):
        return obj.read_at is not None
