from rest_framework import serializers

from access_control.constants import ROLE_LABELS
from access_control.models import UserRole
from core.scoping import (
    get_accessible_organizations,
    get_effective_permissions,
    get_teaching_class_ids,
    is_admin_sistema,
    user_requires_context_selection,
)
from organizations.models import OrganizationMembership

from .models import User


def resolve_active_organization_from_user(user, request=None):
    from core.tenant import resolve_active_organization

    if request is not None:
        try:
            return resolve_active_organization(request, required=False)
        except Exception:
            pass
    if user.active_organization_id:
        return user.active_organization
    accessible = list(get_accessible_organizations(user))
    if len(accessible) == 1:
        return accessible[0]
    return None


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
    papeis_detalhados = serializers.SerializerMethodField()
    organizacoes_disponiveis = serializers.SerializerMethodField()
    organizacao_ativa = serializers.SerializerMethodField()
    requer_selecao_contexto = serializers.SerializerMethodField()
    permissoes = serializers.SerializerMethodField()
    turmas = serializers.SerializerMethodField()
    is_admin_sistema = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'nome',
            'email',
            'is_active',
            'papeis',
            'papeis_detalhados',
            'organizacoes_disponiveis',
            'organizacao_ativa',
            'requer_selecao_contexto',
            'permissoes',
            'turmas',
            'is_admin_sistema',
        ]

    def _serialize_org(self, org):
        return {
            'id': org.id,
            'nome': org.nome,
            'tipo': org.tipo,
            'parent_id': org.parent_id,
            'parent_nome': org.parent.nome if org.parent_id else None,
        }

    def get_papeis(self, obj):
        return list(
            UserRole.objects.filter(user=obj, ativo=True)
            .select_related('role')
            .values_list('role__nome', flat=True)
            .distinct()
        )

    def get_papeis_detalhados(self, obj):
        payload = []
        for user_role in UserRole.objects.filter(user=obj, ativo=True).select_related('role', 'organization'):
            payload.append(
                {
                    'nome': user_role.role.nome,
                    'label': ROLE_LABELS.get(user_role.role.nome, user_role.role.nome),
                    'organization_id': user_role.organization_id,
                }
            )
        return payload

    def get_organizacoes_disponiveis(self, obj):
        return [self._serialize_org(org) for org in get_accessible_organizations(obj)]

    def get_organizacao_ativa(self, obj):
        request = self.context.get('request')
        active_org = resolve_active_organization_from_user(obj, request)
        if not active_org:
            return None
        return self._serialize_org(active_org)

    def get_requer_selecao_contexto(self, obj):
        if user_requires_context_selection(obj):
            request = self.context.get('request')
            active_org = resolve_active_organization_from_user(obj, request)
            return active_org is None
        return False

    def get_permissoes(self, obj):
        request = self.context.get('request')
        active_org = resolve_active_organization_from_user(obj, request)
        if active_org:
            return get_effective_permissions(obj, active_org)

        from access_control.constants import ROLE_SECRETARIO_CAMPO, ROLE_SECRETARIO_IGREJA
        from access_control.models import UserRole

        campo_role = (
            UserRole.objects.filter(
                user=obj,
                ativo=True,
                role__nome=ROLE_SECRETARIO_CAMPO,
                organization__isnull=False,
            )
            .select_related('organization')
            .first()
        )
        if campo_role:
            return get_effective_permissions(obj, campo_role.organization)

        igreja_role = (
            UserRole.objects.filter(
                user=obj,
                ativo=True,
                role__nome=ROLE_SECRETARIO_IGREJA,
                organization__isnull=False,
            )
            .select_related('organization')
            .first()
        )
        if igreja_role:
            return get_effective_permissions(obj, igreja_role.organization)

        return {}

    def get_turmas(self, obj):
        request = self.context.get('request')
        active_org = resolve_active_organization_from_user(obj, request)
        if not active_org:
            return []
        from classrooms.models import ClassGroup

        class_ids = get_teaching_class_ids(obj, active_org)
        if not class_ids:
            return []
        return [
            {'id': turma.id, 'nome': turma.nome}
            for turma in ClassGroup.objects.filter(id__in=class_ids).order_by('nome')
        ]

    def get_is_admin_sistema(self, obj):
        return is_admin_sistema(obj)


class UserContextUpdateSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()

    def validate_organization_id(self, value):
        user = self.context['request'].user
        from core.scoping import can_access_organization

        if not can_access_organization(user, value):
            raise serializers.ValidationError('Organização fora do escopo do usuário.')
        return value
