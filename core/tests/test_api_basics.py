from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from lessons.models import Lesson
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership


class ApiBasicsTests(APITestCase):
    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo Teste',
            sigla='CT',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.org = Organization.objects.create(
            nome='Org Teste',
            sigla='OT',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.user = User.objects.create_user(email='admin@test.com', password='123456', nome='Admin Teste')
        OrganizationMembership.objects.create(user=self.user, organization=self.org, ativo=True)

        role = Role.objects.create(nome='ADMINISTRADOR')
        permission = ModulePermission.objects.create(
            modulo='licoes', visualizar=True, criar=True, editar=True, excluir=True, aprovar=True
        )
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(user=self.user, role=role, organization=self.org, ativo=True)

        login = self.client.post('/api/v1/auth/login', {'email': 'admin@test.com', 'password': '123456'}, format='json')
        self.token = login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}', HTTP_X_ORGANIZATION_ID=str(self.org.id))

    def test_health_endpoint(self):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')

    def test_me_endpoint(self):
        response = self.client.get('/api/v1/me')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'admin@test.com')
        self.assertIn('organizacoes_disponiveis', response.data)

    def test_lessons_list_scoped_by_organization(self):
        Lesson.objects.create(
            organization=self.org,
            numero=1,
            tema='Lição da org',
            data=date.today(),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )
        other_campo = Organization.objects.create(
            nome='Outro Campo', sigla='OC', tipo=TIPO_CAMPO, formato=FORMATO_CAMPO, cidade='Teresina', uf='PI', status='ATIVA'
        )
        other_org = Organization.objects.create(
            nome='Outra Org', sigla='OO', tipo=TIPO_IGREJA, parent=other_campo, cidade='Teresina', uf='PI', status='ATIVA'
        )
        Lesson.objects.create(
            organization=other_org,
            numero=1,
            tema='Lição de outra org',
            data=date.today(),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )

        response = self.client.get('/api/v1/lessons/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['tema'], 'Lição da org')
