from django.db import transaction
from rest_framework import serializers

from access_control.constants import (
    CANONICAL_ROLES,
    ROLE_ADMINISTRADOR,
    ROLE_LABELS,
    ROLE_PROFESSOR,
    ROLE_SECRETARIO_CAMPO,
    ROLE_SECRETARIO_IGREJA,
)
from access_control.models import Role, UserRole
from core.scoping import (
    get_accessible_organizations,
    get_creatable_user_roles,
    get_effective_permissions,
    get_teaching_class_ids,
    is_admin_sistema,
    is_campo_organization,
    is_organization_contract_active,
    user_requires_context_selection,
)
from core.tenant import resolve_active_organization
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
        from organizations.models import Organization

        org = Organization.objects.filter(id=user.active_organization_id).select_related('parent').first()
        if org and is_organization_contract_active(org):
            return org
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
    senha = serializers.CharField(write_only=True, min_length=6, default='123456')
    papel = serializers.ChoiceField(choices=[(role, role) for role in CANONICAL_ROLES])

    class Meta:
        model = User
        fields = ['id', 'nome', 'email', 'is_active', 'senha', 'papel']

    def validate_papel(self, value):
        request = self.context.get('request')
        if request and value == ROLE_ADMINISTRADOR and not is_admin_sistema(request.user):
            raise serializers.ValidationError('Sem permissão para criar administrador do sistema.')
        if request and not is_admin_sistema(request.user):
            allowed_roles = get_creatable_user_roles(request.user)
            if value not in allowed_roles:
                raise serializers.ValidationError('Sem permissão para criar este perfil.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value.strip()).exists():
            raise serializers.ValidationError('Já existe um usuário com este e-mail.')
        return value.strip().lower()

    def validate(self, attrs):
        request = self.context.get('request')
        if not request:
            return attrs

        papel = attrs.get('papel')
        if papel == ROLE_ADMINISTRADOR:
            return attrs

        org = resolve_active_organization(request, required=False)
        if not org:
            raise serializers.ValidationError({'detail': 'Selecione uma organização no contexto.'})

        if papel in (ROLE_SECRETARIO_IGREJA, ROLE_PROFESSOR) and is_campo_organization(org):
            raise serializers.ValidationError(
                {'papel': 'Selecione uma igreja no contexto para este perfil.'}
            )
        if papel == ROLE_SECRETARIO_CAMPO and not is_campo_organization(org):
            raise serializers.ValidationError({'papel': 'Secretário de campo exige contexto de campo.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        papel = validated_data.pop('papel')
        password = validated_data.pop('senha')
        request = self.context.get('request')

        user = User.objects.create_user(password=password, **validated_data)

        if papel == ROLE_ADMINISTRADOR:
            role_org = None
        else:
            org = resolve_active_organization(request, required=True)
            role_org = org

            OrganizationMembership.objects.update_or_create(
                user=user,
                organization=org,
                defaults={'ativo': True, 'role_scope': papel.lower()},
            )

        role = Role.objects.filter(nome=papel, ativo=True).first()
        if not role:
            raise serializers.ValidationError({'papel': 'Perfil não encontrado.'})

        UserRole.objects.create(user=user, role=role, organization=role_org, ativo=True)

        if papel in (ROLE_SECRETARIO_CAMPO, ROLE_SECRETARIO_IGREJA) and not user.is_staff:
            user.is_staff = True
            user.save(update_fields=['is_staff'])

        return user


class MeSerializer(serializers.ModelSerializer):
    papeis = serializers.SerializerMethodField()
    papeis_detalhados = serializers.SerializerMethodField()
    organizacoes_disponiveis = serializers.SerializerMethodField()
    organizacao_ativa = serializers.SerializerMethodField()
    requer_selecao_contexto = serializers.SerializerMethodField()
    permissoes = serializers.SerializerMethodField()
    turmas = serializers.SerializerMethodField()
    is_admin_sistema = serializers.SerializerMethodField()
    acesso_bloqueado = serializers.SerializerMethodField()
    motivo_bloqueio = serializers.SerializerMethodField()
    foto_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'nome',
            'email',
            'is_active',
            'foto_url',
            'papeis',
            'papeis_detalhados',
            'organizacoes_disponiveis',
            'organizacao_ativa',
            'requer_selecao_contexto',
            'permissoes',
            'turmas',
            'is_admin_sistema',
            'acesso_bloqueado',
            'motivo_bloqueio',
        ]

    def get_foto_url(self, obj):
        if not obj.foto:
            return None
        request = self.context.get('request')
        url = obj.foto.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def _serialize_org(self, org):
        return {
            'id': org.id,
            'nome': org.nome,
            'tipo': org.tipo,
            'formato': org.formato or '',
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

    def get_acesso_bloqueado(self, obj):
        if is_admin_sistema(obj):
            return False
        if not obj.is_active:
            return True
        if get_accessible_organizations(obj):
            return False
        has_org_role = UserRole.objects.filter(user=obj, ativo=True, organization_id__isnull=False).exists()
        return has_org_role

    def get_motivo_bloqueio(self, obj):
        if not self.get_acesso_bloqueado(obj):
            return None
        if not obj.is_active:
            return 'USUARIO_INATIVO'
        return 'ORGANIZACAO_INATIVA'


class UserContextUpdateSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()

    def validate_organization_id(self, value):
        user = self.context['request'].user
        from core.scoping import can_access_organization, is_organization_contract_active
        from organizations.models import Organization

        if not can_access_organization(user, value):
            org = Organization.objects.filter(id=value).select_related('parent').first()
            if org and not is_organization_contract_active(org):
                raise serializers.ValidationError('O acesso a esta organização está suspenso.')
            raise serializers.ValidationError('Organização fora do escopo do usuário.')
        return value


class MeUpdateSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=255)

    def validate_nome(self, value):
        nome = value.strip()
        if len(nome) < 2:
            raise serializers.ValidationError('O nome deve ter pelo menos 2 caracteres.')
        return nome


class MeChangePasswordSerializer(serializers.Serializer):
    senha_atual = serializers.CharField(write_only=True)
    nova_senha = serializers.CharField(write_only=True, min_length=6)
    confirmar_senha = serializers.CharField(write_only=True, min_length=6)

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs['senha_atual']):
            raise serializers.ValidationError({'senha_atual': 'Senha atual incorreta.'})
        if attrs['nova_senha'] != attrs['confirmar_senha']:
            raise serializers.ValidationError({'confirmar_senha': 'As senhas não coincidem.'})
        return attrs


ALLOWED_AVATAR_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024


class MeAvatarSerializer(serializers.Serializer):
    foto = serializers.ImageField()

    def validate_foto(self, value):
        content_type = getattr(value, 'content_type', None)
        if content_type and content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
            raise serializers.ValidationError('Formato inválido. Use JPEG, PNG ou WebP.')
        if value.size > MAX_AVATAR_SIZE_BYTES:
            raise serializers.ValidationError('A imagem deve ter no máximo 5 MB.')
        return value
