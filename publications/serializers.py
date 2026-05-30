from rest_framework import serializers

from .models import PublicationControl


class PublicationControlSerializer(serializers.ModelSerializer):
    turma_nome = serializers.CharField(source='class_group.nome', read_only=True)
    trimestre_numero = serializers.IntegerField(source='trimester.numero', read_only=True)
    trimestre_ano = serializers.IntegerField(source='trimester.ano', read_only=True)

    class Meta:
        model = PublicationControl
        fields = [
            'id',
            'organization',
            'trimester',
            'trimestre_numero',
            'trimestre_ano',
            'class_group',
            'turma_nome',
            'person_type',
            'person_name',
            'student',
            'professor',
            'recebeu',
            'pagou',
            'metodo_pagamento',
            'is_active',
        ]
        read_only_fields = ['organization', 'trimester']
