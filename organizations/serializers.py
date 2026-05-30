from rest_framework import serializers

from organizations.constants import (
    FORMATO_CAMPO,
    FORMATO_IGREJA_INDIVIDUAL,
    TIPO_CAMPO,
    TIPO_IGREJA,
)

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


class InstanceOrganizationSerializer(serializers.ModelSerializer):
    parent_nome = serializers.CharField(source='parent.nome', read_only=True)
    igrejas_count = serializers.SerializerMethodField()

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
            'igrejas_count',
            'created_at',
            'updated_at',
        ]

    def get_igrejas_count(self, obj):
        if obj.tipo != TIPO_CAMPO:
            return 0
        return Organization.objects.filter(parent=obj, tipo=TIPO_IGREJA).count()


class InstanceOrganizationCreateSerializer(serializers.ModelSerializer):
    formato = serializers.ChoiceField(choices=[FORMATO_CAMPO, FORMATO_IGREJA_INDIVIDUAL])

    class Meta:
        model = Organization
        fields = ['nome', 'sigla', 'formato', 'cidade', 'uf', 'responsavel', 'membros']

    def create(self, validated_data):
        formato = validated_data.pop('formato')
        if formato == FORMATO_CAMPO:
            validated_data['tipo'] = TIPO_CAMPO
            validated_data['formato'] = FORMATO_CAMPO
        else:
            validated_data['tipo'] = TIPO_IGREJA
            validated_data['formato'] = FORMATO_IGREJA_INDIVIDUAL
        validated_data['parent'] = None
        validated_data.setdefault('status', 'ATIVA')
        validated_data.setdefault('membros', 0)
        validated_data.setdefault('responsavel', '')
        return Organization.objects.create(**validated_data)


class InstanceOrganizationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['nome', 'sigla', 'cidade', 'uf', 'responsavel', 'membros']


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
