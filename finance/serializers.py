from rest_framework import serializers

from .models import Offering


class OfferingSerializer(serializers.ModelSerializer):
    turma_nome = serializers.CharField(source='class_group.nome', read_only=True)
    licao_tema = serializers.CharField(source='lesson.tema', read_only=True)

    class Meta:
        model = Offering
        fields = [
            'id',
            'organization',
            'lesson',
            'licao_tema',
            'class_group',
            'turma_nome',
            'data',
            'valor',
            'is_active',
        ]
        read_only_fields = ['organization']

    def validate_valor(self, value):
        if value < 0:
            raise serializers.ValidationError('Oferta não pode ser negativa.')
        return value
