from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from core.scoping import get_accessible_organization_ids, is_organization_contract_active
from organizations.constants import FORMATO_CAMPO, FORMATO_IGREJA_INDIVIDUAL, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership


class InstanceOrganizationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin.instances@test.com',
            password='123456',
            nome='Admin Sistema',
            is_superuser=True,
        )
        self.campo = Organization.objects.create(
            nome='Campo Instâncias',
            sigla='CI',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.igreja_filha = Organization.objects.create(
            nome='Igreja Filha',
            sigla='IF',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.secretario_campo = User.objects.create_user(
            email='sec.instancias@test.com',
            password='123456',
            nome='Secretário Campo',
        )
        role_campo = Role.objects.create(nome='SECRETARIO_CAMPO')
        org_perm, _ = ModulePermission.objects.get_or_create(
            modulo='organizacoes',
            defaults={
                'visualizar': True,
                'criar': True,
                'editar': True,
                'excluir': True,
                'aprovar': True,
            },
        )
        RolePermission.objects.get_or_create(role=role_campo, permission=org_perm)
        UserRole.objects.create(
            user=self.secretario_campo,
            role=role_campo,
            organization=self.campo,
            ativo=True,
        )
        OrganizationMembership.objects.create(
            user=self.secretario_campo,
            organization=self.campo,
            ativo=True,
        )

        login_admin = self.client.post(
            '/api/v1/auth/login',
            {'email': 'admin.instances@test.com', 'password': '123456'},
            format='json',
        )
        self.admin_token = login_admin.data['access']

        login_sec = self.client.post(
            '/api/v1/auth/login',
            {'email': 'sec.instancias@test.com', 'password': '123456'},
            format='json',
        )
        self.sec_token = login_sec.data['access']

    def _admin_auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')

    def _sec_auth(self, org_id):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.sec_token}',
            HTTP_X_ORGANIZATION_ID=str(org_id),
        )

    def test_admin_creates_campo_instance(self):
        self._admin_auth()
        response = self.client.post(
            '/api/v1/organizations/',
            {
                'nome': 'Novo Campo',
                'sigla': 'NC',
                'formato': FORMATO_CAMPO,
                'cidade': 'Timon',
                'uf': 'MA',
                'responsavel': 'Pr. Teste',
                'membros': 100,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['tipo'], TIPO_CAMPO)
        self.assertEqual(response.data['formato'], FORMATO_CAMPO)

    def test_admin_creates_igreja_individual(self):
        self._admin_auth()
        response = self.client.post(
            '/api/v1/organizations/',
            {
                'nome': 'Igreja Solo',
                'sigla': 'SOLO',
                'formato': FORMATO_IGREJA_INDIVIDUAL,
                'cidade': 'Parnaíba',
                'uf': 'PI',
                'responsavel': 'Pr. Solo',
                'membros': 50,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['tipo'], TIPO_IGREJA)
        self.assertEqual(response.data['formato'], FORMATO_IGREJA_INDIVIDUAL)

    def test_deactivate_campo_blocks_child_contract(self):
        self.assertTrue(is_organization_contract_active(self.igreja_filha))
        self.campo.is_active = False
        self.campo.status = 'INATIVA'
        self.campo.save(update_fields=['is_active', 'status'])
        self.igreja_filha.refresh_from_db()
        self.assertFalse(is_organization_contract_active(self.igreja_filha))

    def test_secretario_loses_access_when_campo_deactivated(self):
        self.campo.is_active = False
        self.campo.status = 'INATIVA'
        self.campo.save(update_fields=['is_active', 'status'])
        org_ids = get_accessible_organization_ids(self.secretario_campo)
        self.assertEqual(org_ids, [])

    def test_me_returns_acesso_bloqueado_for_secretario(self):
        self.campo.is_active = False
        self.campo.status = 'INATIVA'
        self.campo.save(update_fields=['is_active', 'status'])
        self._sec_auth(self.campo.id)
        response = self.client.get('/api/v1/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['acesso_bloqueado'])
        self.assertEqual(response.data['motivo_bloqueio'], 'ORGANIZACAO_INATIVA')

    def test_reactivate_campo_restores_access(self):
        self._admin_auth()
        deactivate = self.client.post(f'/api/v1/organizations/{self.campo.id}/deactivate/')
        self.assertEqual(deactivate.status_code, status.HTTP_200_OK)
        org_ids = get_accessible_organization_ids(self.secretario_campo)
        self.assertEqual(org_ids, [])

        activate = self.client.post(f'/api/v1/organizations/{self.campo.id}/activate/')
        self.assertEqual(activate.status_code, status.HTTP_200_OK)
        org_ids = get_accessible_organization_ids(self.secretario_campo)
        self.assertIn(self.campo.id, org_ids)
        self.assertIn(self.igreja_filha.id, org_ids)

    def test_individual_igreja_deactivate_blocks_only_itself(self):
        standalone = Organization.objects.create(
            nome='Igreja Individual Test',
            sigla='IIT',
            tipo=TIPO_IGREJA,
            formato=FORMATO_IGREJA_INDIVIDUAL,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        secretario = User.objects.create_user(
            email='sec.igreja.ind@test.com',
            password='123456',
            nome='Secretário Igreja',
        )
        role = Role.objects.create(nome='SECRETARIO_IGREJA')
        org_perm = ModulePermission.objects.get(modulo='organizacoes')
        RolePermission.objects.get_or_create(role=role, permission=org_perm)
        UserRole.objects.create(user=secretario, role=role, organization=standalone, ativo=True)

        self._admin_auth()
        response = self.client.post(f'/api/v1/organizations/{standalone.id}/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(get_accessible_organization_ids(secretario), [])

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.sec_token}')
        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'sec.igreja.ind@test.com', 'password': '123456'},
            format='json',
        )
        token = login.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token}',
            HTTP_X_ORGANIZATION_ID=str(standalone.id),
        )
        me = self.client.get('/api/v1/me/')
        self.assertTrue(me.data['acesso_bloqueado'])
