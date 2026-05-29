from rest_framework import serializers

from organizations.constants import TIPO_IGREJA

from .models import Organization, OrganizationMembership


class OrganizationSerializer(serializers.ModelSerializer):
    parent_nome = serializers.CharField(source='parent.nome', read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id',
            'nome',
            'sigla',
            'tipo',
            'formato',
            'parent',
            'parent_nome',
            'cidade',
            'uf',
            'responsavel',
            'membros',
            'status',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['tipo', 'formato', 'parent', 'created_at', 'updated_at']


class ChurchSerializer(serializers.ModelSerializer):
    parent_nome = serializers.CharField(source='parent.nome', read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id',
            'nome',
            'sigla',
            'tipo',
            'parent',
            'parent_nome',
            'cidade',
            'uf',
            'responsavel',
            'membros',
            'status',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['tipo', 'parent', 'parent_nome', 'created_at', 'updated_at']

    def validate(self, attrs):
        attrs['tipo'] = TIPO_IGREJA
        return attrs


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationMembership
        fields = ['id', 'user', 'organization', 'role_scope', 'ativo']
