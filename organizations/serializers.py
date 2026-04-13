from rest_framework import serializers

from .models import Organization, OrganizationMembership


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            'id',
            'nome',
            'sigla',
            'tipo',
            'cidade',
            'uf',
            'responsavel',
            'membros',
            'status',
            'is_active',
            'created_at',
            'updated_at',
        ]


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationMembership
        fields = ['id', 'user', 'organization', 'role_scope', 'ativo']
