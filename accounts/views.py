from django.db.models import Prefetch
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.scoping import get_org_descendant_ids, is_admin_sistema, is_campo_organization
from core.tenant import get_user_organization, resolve_active_organization
from access_control.models import UserRole
from classrooms.models import ClassTeacher
from organizations.models import Organization, OrganizationMembership

from .models import User
from .serializers import (
    MeAvatarSerializer,
    MeChangePasswordSerializer,
    MeSerializer,
    MeUpdateSerializer,
    UserContextUpdateSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class UserViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    search_fields = ['nome', 'email', 'user_roles__role__nome']

    def get_queryset(self):
        org = resolve_active_organization(self.request, required=False)
        if org is None:
            # Sem contexto ativo (ex.: admin do sistema numa instalação nova).
            if is_admin_sistema(self.request.user):
                queryset = User.objects.all().order_by('nome')
            else:
                return User.objects.none()
        else:
            org_ids = get_org_descendant_ids(org) if is_campo_organization(org) else [org.id]
            user_ids = OrganizationMembership.objects.filter(
                organization_id__in=org_ids,
                ativo=True,
            ).values_list('user_id', flat=True)
            queryset = User.objects.filter(id__in=user_ids).order_by('nome')

        role_name = self.request.query_params.get('role')
        if role_name:
            queryset = queryset.filter(
                user_roles__ativo=True,
                user_roles__role__nome=role_name.strip().upper(),
            ).distinct()
        return queryset.prefetch_related(
            Prefetch(
                'user_roles',
                queryset=UserRole.objects.filter(ativo=True).select_related('role'),
                to_attr='active_roles_prefetched',
            ),
            Prefetch(
                'organization_memberships',
                queryset=OrganizationMembership.objects.filter(ativo=True).select_related(
                    'organization'
                ),
                to_attr='active_memberships_prefetched',
            ),
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'stats']:
            permission_classes = [IsAuthenticated, module_permission('usuarios', 'visualizar')]
        elif self.action == 'create':
            permission_classes = [IsAuthenticated, module_permission('usuarios', 'criar')]
        elif self.action in ['partial_update', 'update', 'reset_password']:
            permission_classes = [IsAuthenticated, module_permission('usuarios', 'editar')]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(methods=['GET'], detail=False)
    def stats(self, request):
        queryset = self.get_queryset()
        return Response(
            {
                'total': queryset.count(),
                'ativos': queryset.filter(is_active=True).count(),
                'inativos': queryset.filter(is_active=False).count(),
            }
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        output = UserSerializer(user, context={'request': request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=True, url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        user = self.get_object()
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        if not user.is_active:
            org = get_user_organization(request)
            org_ids = get_org_descendant_ids(org) if is_campo_organization(org) else [org.id]
            ClassTeacher.objects.filter(
                user=user,
                class_group__organization_id__in=org_ids,
            ).delete()
        return Response({'id': user.id, 'is_active': user.is_active})

    @action(methods=['POST'], detail=True, url_path='reset-password')
    def reset_password(self, request, pk=None):
        user = self.get_object()
        user.set_password('123456')
        user.save(update_fields=['password'])
        return Response({'id': user.id, 'detail': 'Senha redefinida para 123456.'})


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def me(request):
    if request.method == 'GET':
        return Response(MeSerializer(request.user, context={'request': request}).data)

    serializer = MeUpdateSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = request.user
    user.nome = serializer.validated_data['nome']
    user.save(update_fields=['nome', 'first_name', 'last_name', 'username'])
    return Response(MeSerializer(user, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = MeChangePasswordSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = request.user
    user.set_password(serializer.validated_data['nova_senha'])
    user.save(update_fields=['password'])
    return Response({'detail': 'Senha alterada com sucesso.'})


def _delete_user_foto(user):
    if user.foto:
        user.foto.delete(save=False)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def me_avatar(request):
    user = request.user

    if request.method == 'DELETE':
        _delete_user_foto(user)
        user.foto = None
        user.save(update_fields=['foto'])
        return Response(MeSerializer(user, context={'request': request}).data)

    serializer = MeAvatarSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    _delete_user_foto(user)
    user.foto = serializer.validated_data['foto']
    user.save(update_fields=['foto'])
    return Response(MeSerializer(user, context={'request': request}).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_context(request):
    serializer = UserContextUpdateSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    organization = Organization.objects.get(id=serializer.validated_data['organization_id'])
    request.user.active_organization = organization
    request.user.save(update_fields=['active_organization'])
    return Response(MeSerializer(request.user, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    response = Response({'detail': 'Logout realizado com sucesso.'}, status=status.HTTP_200_OK)
    response.delete_cookie('access_token', path='/')
    response.delete_cookie('refresh_token', path='/')
    return response
