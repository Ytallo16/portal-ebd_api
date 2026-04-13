from rest_framework import serializers

from access_control.models import UserRole
from organizations.models import OrganizationMembership

from .models import User


class UserSerializer(serializers.ModelSerializer):
    papeis = serializers.SerializerMethodField()
    organizacoes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'nome', 'email', 'is_active', 'date_joined', 'papeis', 'organizacoes']

    def get_papeis(self, obj):
        return list(
            UserRole.objects.filter(user=obj, ativo=True)
            .select_related('role')
            .values_list('role__nome', flat=True)
        )

    def get_organizacoes(self, obj):
        return list(
            OrganizationMembership.objects.filter(user=obj, ativo=True)
            .select_related('organization')
            .values('organization_id', 'organization__nome')
        )


class UserCreateSerializer(serializers.ModelSerializer):
    senha = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['id', 'nome', 'email', 'is_active', 'senha']

    def create(self, validated_data):
        password = validated_data.pop('senha')
        return User.objects.create_user(password=password, **validated_data)


class MeSerializer(serializers.ModelSerializer):
    papeis = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'nome', 'email', 'is_active', 'papeis']

    def get_papeis(self, obj):
        return list(
            UserRole.objects.filter(user=obj, ativo=True)
            .select_related('role')
            .values_list('role__nome', flat=True)
        )
