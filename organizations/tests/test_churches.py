from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from organizations.constants import FORMATO_CAMPO, FORMATO_IGREJA_INDIVIDUAL, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership


class ChurchApiTests(APITestCase):
    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo Churches',
            sigla='CC',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.igreja = Organization.objects.create(
            nome='Igreja Churches',
            sigla='IC',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.standalone = Organization.objects.create(
            nome='Igreja Standalone',
            sigla='IS',
            tipo=TIPO_IGREJA,
            formato=FORMATO_IGREJA_INDIVIDUAL,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )

        self.secretario_campo = User.objects.create_user(
            email='sec.campo.churches@test.com',
            password='123456',
            nome='Secretário Campo',
        )
        OrganizationMembership.objects.create(
            user=self.secretario_campo,
            organization=self.campo,
            ativo=True,
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

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'sec.campo.churches@test.com', 'password': '123456'},
            format='json',
        )
        self.token = login.data['access']

    def _auth(self, org_id):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
            HTTP_X_ORGANIZATION_ID=str(org_id),
        )

    def test_list_churches_with_campo_context(self):
        self._auth(self.campo.id)
        response = self.client.get('/api/v1/organizations/churches/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if isinstance(response.data, dict) else response.data
        names = {item['nome'] for item in results}
        self.assertIn('Igreja Churches', names)

    def test_create_church_under_campo(self):
        self._auth(self.campo.id)
        response = self.client.post(
            '/api/v1/organizations/churches/',
            {
                'nome': 'Nova Igreja',
                'sigla': 'NI',
                'cidade': 'Teresina',
                'uf': 'PI',
                'responsavel': 'Pr. Teste',
                'membros': 10,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Organization.objects.get(sigla='NI')
        self.assertEqual(created.parent_id, self.campo.id)
        self.assertEqual(created.tipo, TIPO_IGREJA)

    def test_list_churches_with_igreja_context_uses_parent_campo(self):
        self._auth(self.igreja.id)
        response = self.client.get('/api/v1/organizations/churches/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {item['nome'] for item in response.data['results']}
        self.assertIn('Igreja Churches', names)

    def test_churches_rejected_for_standalone_igreja(self):
        user = User.objects.create_user(
            email='standalone.churches@test.com',
            password='123456',
            nome='Standalone',
        )
        OrganizationMembership.objects.create(user=user, organization=self.standalone, ativo=True)
        role = Role.objects.create(nome='SECRETARIO_IGREJA')
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
        RolePermission.objects.get_or_create(role=role, permission=org_perm)
        UserRole.objects.create(user=user, role=role, organization=self.standalone, ativo=True)

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'standalone.churches@test.com', 'password': '123456'},
            format='json',
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}',
            HTTP_X_ORGANIZATION_ID=str(self.standalone.id),
        )
        response = self.client.get('/api/v1/organizations/churches/')
        self.assertIn(response.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))

    def test_campo_context_blocks_operational_lessons(self):
        self._auth(self.campo.id)
        response = self.client.get('/api/v1/lessons/')
        self.assertIn(response.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))
