from rest_framework import serializers

from .models import PublicationControl


class PublicationControlSerializer(serializers.ModelSerializer):
    turma_nome = serializers.CharField(source='class_group.nome', read_only=True)

    class Meta:
        model = PublicationControl
        fields = [
            'id',
            'organization',
            'class_group',
            'turma_nome',
            'person_type',
            'person_name',
            'student',
            'professor',
            'recebeu',
            'pagou',
            'is_active',
        ]
        read_only_fields = ['organization']
