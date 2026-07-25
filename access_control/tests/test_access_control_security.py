from rest_framework import status
from rest_framework.test import APITestCase

from access_control.constants import (
    ROLE_ADMINISTRADOR,
    ROLE_PROFESSOR,
    ROLE_SECRETARIO_CAMPO,
    ROLE_SECRETARIO_IGREJA,
)
from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership


class AccessControlSecurityTests(APITestCase):
    def setUp(self):
        self.campo_a = self._create_campo('Campo A', 'CA')
        self.igreja_a = self._create_igreja('Igreja A', 'IA', self.campo_a)
        self.igreja_a_2 = self._create_igreja('Igreja A 2', 'IA2', self.campo_a)
        self.campo_b = self._create_campo('Campo B', 'CB')
        self.igreja_b = self._create_igreja('Igreja B', 'IB', self.campo_b)

        self.admin_role = Role.objects.create(nome=ROLE_ADMINISTRADOR)
        self.secretario_campo_role = Role.objects.create(nome=ROLE_SECRETARIO_CAMPO)
        self.secretario_igreja_role = Role.objects.create(nome=ROLE_SECRETARIO_IGREJA)
        self.professor_role = Role.objects.create(nome=ROLE_PROFESSOR)

        self.usuarios_permission = ModulePermission.objects.create(
            modulo='usuarios',
            visualizar=True,
            criar=True,
            editar=True,
            excluir=True,
            aprovar=True,
        )
        self.alunos_permission = ModulePermission.objects.create(
            modulo='alunos',
            visualizar=True,
        )
        RolePermission.objects.create(
            role=self.secretario_campo_role,
            permission=self.usuarios_permission,
        )
        RolePermission.objects.create(
            role=self.secretario_igreja_role,
            permission=self.usuarios_permission,
        )

        self.admin = self._create_user('admin@teste.com', 'Administrador')
        UserRole.objects.create(
            user=self.admin,
            role=self.admin_role,
            organization=None,
            ativo=True,
        )

        self.secretario_campo = self._create_user('campo@teste.com', 'Secretário Campo')
        self._add_membership(self.secretario_campo, self.campo_a)
        UserRole.objects.create(
            user=self.secretario_campo,
            role=self.secretario_campo_role,
            organization=self.campo_a,
            ativo=True,
        )

        self.secretario_igreja = self._create_user('igreja@teste.com', 'Secretário Igreja')
        self._add_membership(self.secretario_igreja, self.igreja_a)
        UserRole.objects.create(
            user=self.secretario_igreja,
            role=self.secretario_igreja_role,
            organization=self.igreja_a,
            ativo=True,
        )

        self.usuario_local = self._create_user('local@teste.com', 'Usuário Local')
        self._add_membership(self.usuario_local, self.igreja_a)

        self.usuario_descendente = self._create_user(
            'descendente@teste.com',
            'Usuário Descendente',
        )
        self._add_membership(self.usuario_descendente, self.igreja_a_2)

        self.usuario_sem_vinculo = self._create_user(
            'sem-vinculo@teste.com',
            'Usuário Sem Vínculo',
        )

        self.usuario_externo = self._create_user('externo@teste.com', 'Usuário Externo')
        self._add_membership(self.usuario_externo, self.igreja_b)
        self.papel_externo = UserRole.objects.create(
            user=self.usuario_externo,
            role=self.professor_role,
            organization=self.igreja_b,
            ativo=True,
        )

    def _create_campo(self, nome, sigla):
        return Organization.objects.create(
            nome=nome,
            sigla=sigla,
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )

    def _create_igreja(self, nome, sigla, campo):
        return Organization.objects.create(
            nome=nome,
            sigla=sigla,
            tipo=TIPO_IGREJA,
            parent=campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )

    def _create_user(self, email, nome):
        return User.objects.create_user(email=email, password='123456', nome=nome)

    def _add_membership(self, user, organization):
        return OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            ativo=True,
        )

    def _authenticate(self, user, organization=None):
        self.client.force_authenticate(user=user)
        if organization is None:
            self.client.credentials()
        else:
            self.client.credentials(HTTP_X_ORGANIZATION_ID=str(organization.id))

    def test_only_global_admin_can_replace_role_permissions(self):
        url = f'/api/v1/roles/{self.professor_role.id}/permissions/'
        payload = {'permission_ids': [self.alunos_permission.id]}

        self._authenticate(self.secretario_igreja, self.igreja_a)
        denied = self.client.put(url, payload, format='json')

        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            RolePermission.objects.filter(
                role=self.professor_role,
                permission=self.alunos_permission,
            ).exists()
        )

        self._authenticate(self.admin)
        allowed = self.client.put(url, payload, format='json')

        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertTrue(
            RolePermission.objects.filter(
                role=self.professor_role,
                permission=self.alunos_permission,
            ).exists()
        )

    def test_role_permission_replacement_is_atomic_for_invalid_ids(self):
        RolePermission.objects.create(
            role=self.professor_role,
            permission=self.alunos_permission,
        )
        self._authenticate(self.admin)

        response = self.client.put(
            f'/api/v1/roles/{self.professor_role.id}/permissions/',
            {'permission_ids': [999999]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            RolePermission.objects.filter(
                role=self.professor_role,
                permission=self.alunos_permission,
            ).exists()
        )

    def test_only_global_admin_can_change_role_definitions(self):
        url = f'/api/v1/roles/{self.professor_role.id}/'

        self._authenticate(self.secretario_igreja, self.igreja_a)
        denied = self.client.patch(url, {'descricao': 'Alterada'}, format='json')
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self._authenticate(self.admin)
        allowed = self.client.patch(url, {'descricao': 'Alterada'}, format='json')
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

        self.professor_role.refresh_from_db()
        self.assertEqual(self.professor_role.descricao, 'Alterada')

    def test_module_permission_reads_remain_available_but_writes_require_admin(self):
        self._authenticate(self.secretario_igreja, self.igreja_a)
        read_response = self.client.get('/api/v1/module-permissions/')
        denied_update = self.client.patch(
            f'/api/v1/module-permissions/{self.alunos_permission.id}/',
            {'editar': True},
            format='json',
        )
        denied_create = self.client.post(
            '/api/v1/module-permissions/',
            {'modulo': 'relatorios', 'visualizar': True},
            format='json',
        )

        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(denied_update.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(denied_create.status_code, status.HTTP_403_FORBIDDEN)
        self.alunos_permission.refresh_from_db()
        self.assertFalse(self.alunos_permission.editar)
        self.assertFalse(ModulePermission.objects.filter(modulo='relatorios').exists())

        self._authenticate(self.admin)
        allowed_update = self.client.patch(
            f'/api/v1/module-permissions/{self.alunos_permission.id}/',
            {'editar': True},
            format='json',
        )
        allowed_create = self.client.post(
            '/api/v1/module-permissions/',
            {'modulo': 'relatorios', 'visualizar': True},
            format='json',
        )

        self.assertEqual(allowed_update.status_code, status.HTTP_200_OK)
        self.assertEqual(allowed_create.status_code, status.HTTP_201_CREATED)

    def test_user_role_list_and_objects_are_scoped_to_active_organization(self):
        self._authenticate(self.secretario_igreja, self.igreja_a)

        response = self.client.get('/api/v1/user-roles/')
        external_response = self.client.get(
            f'/api/v1/user-roles/{self.papel_externo.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(
            {item['id'] for item in results},
            {
                UserRole.objects.get(
                    user=self.secretario_igreja,
                    role=self.secretario_igreja_role,
                    organization=self.igreja_a,
                ).id
            },
        )
        self.assertEqual(external_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_admin_cannot_assign_global_admin_or_cross_scope_role(self):
        self._authenticate(self.secretario_igreja, self.igreja_a)

        global_admin_response = self.client.post(
            '/api/v1/user-roles/',
            {
                'user': self.usuario_local.id,
                'role': self.admin_role.id,
                'organization': None,
                'ativo': True,
            },
            format='json',
        )
        cross_scope_response = self.client.post(
            '/api/v1/user-roles/',
            {
                'user': self.usuario_externo.id,
                'role': self.professor_role.id,
                'organization': self.igreja_b.id,
                'ativo': True,
            },
            format='json',
        )

        self.assertEqual(global_admin_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(cross_scope_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            UserRole.objects.filter(
                user=self.usuario_local,
                role=self.admin_role,
                ativo=True,
            ).exists()
        )

    def test_non_admin_can_assign_allowed_role_only_to_organization_member(self):
        self._authenticate(self.secretario_igreja, self.igreja_a)

        no_membership_response = self.client.post(
            '/api/v1/user-roles/',
            {
                'user': self.usuario_sem_vinculo.id,
                'role': self.professor_role.id,
                'organization': self.igreja_a.id,
                'ativo': True,
            },
            format='json',
        )
        allowed_response = self.client.post(
            '/api/v1/user-roles/',
            {
                'user': self.usuario_local.id,
                'role': self.professor_role.id,
                'organization': self.igreja_a.id,
                'ativo': True,
            },
            format='json',
        )

        self.assertEqual(no_membership_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(allowed_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            UserRole.objects.filter(
                user=self.usuario_local,
                role=self.professor_role,
                organization=self.igreja_a,
                ativo=True,
            ).exists()
        )

    def test_field_secretary_can_assign_church_role_inside_its_field(self):
        self._authenticate(self.secretario_campo, self.campo_a)

        response = self.client.post(
            '/api/v1/user-roles/',
            {
                'user': self.usuario_descendente.id,
                'role': self.secretario_igreja_role.id,
                'organization': self.igreja_a_2.id,
                'ativo': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_global_admin_can_assign_and_manage_global_or_external_roles(self):
        self._authenticate(self.admin)

        create_response = self.client.post(
            '/api/v1/user-roles/',
            {
                'user': self.usuario_local.id,
                'role': self.admin_role.id,
                'organization': None,
                'ativo': True,
            },
            format='json',
        )
        update_external_response = self.client.patch(
            f'/api/v1/user-roles/{self.papel_externo.id}/',
            {'ativo': False},
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(update_external_response.status_code, status.HTTP_200_OK)
        self.papel_externo.refresh_from_db()
        self.assertFalse(self.papel_externo.ativo)

    def test_even_global_admin_cannot_create_organization_scoped_admin(self):
        self._authenticate(self.admin)

        response = self.client.post(
            '/api/v1/user-roles/',
            {
                'user': self.usuario_local.id,
                'role': self.admin_role.id,
                'organization': self.igreja_a.id,
                'ativo': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            UserRole.objects.filter(
                user=self.usuario_local,
                role=self.admin_role,
                organization=self.igreja_a,
            ).exists()
        )
