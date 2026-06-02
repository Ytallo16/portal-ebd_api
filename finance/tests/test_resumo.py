from datetime import date
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from classrooms.models import ClassGroup
from finance.models import Offering
from lessons.models import Lesson
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership


class FinanceResumoTests(APITestCase):
    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo Financeiro',
            sigla='CF',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.igreja_a = Organization.objects.create(
            nome='Igreja Alpha',
            sigla='IA',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.igreja_b = Organization.objects.create(
            nome='Igreja Beta',
            sigla='IB',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )

        self.secretario = User.objects.create_user(
            email='sec.fin@test.com',
            password='123456',
            nome='Secretário Campo',
        )
        role = Role.objects.create(nome='SECRETARIO_CAMPO')
        fin_perm = ModulePermission.objects.create(
            modulo='financeiro',
            visualizar=True,
            criar=True,
            editar=True,
            excluir=False,
            aprovar=True,
        )
        RolePermission.objects.create(role=role, permission=fin_perm)
        UserRole.objects.create(user=self.secretario, role=role, organization=self.campo, ativo=True)
        OrganizationMembership.objects.create(user=self.secretario, organization=self.campo, ativo=True)

        self.turma_a = ClassGroup.objects.create(
            organization=self.igreja_a,
            nome='Adultos',
            faixa_etaria='Adultos',
            cor='#125A94',
        )
        self.turma_b = ClassGroup.objects.create(
            organization=self.igreja_b,
            nome='Jovens',
            faixa_etaria='Jovens',
            cor='#068CC3',
        )
        self.lesson_a = Lesson.objects.create(
            organization=self.igreja_a,
            numero=1,
            tema='Tema A',
            data=date(2026, 3, 1),
            revista='Revista',
            trimestre=1,
            ano=2026,
            created_by=self.secretario,
        )

        Offering.objects.create(
            organization=self.igreja_a,
            class_group=self.turma_a,
            lesson=self.lesson_a,
            data=date(2026, 3, 1),
            valor=Decimal('100.00'),
            created_by=self.secretario,
        )
        Offering.objects.create(
            organization=self.igreja_b,
            class_group=self.turma_b,
            lesson=None,
            data=date(2026, 3, 8),
            valor=Decimal('50.00'),
            created_by=self.secretario,
        )

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'sec.fin@test.com', 'password': '123456'},
            format='json',
        )
        self.token = login.data['access']

    def _auth(self, org_id):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
            HTTP_X_ORGANIZATION_ID=str(org_id),
        )

    def test_resumo_campo_returns_por_igreja(self):
        self._auth(self.campo.id)
        response = self.client.get('/api/v1/finance/resumo/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scope'], 'campo')
        self.assertEqual(len(response.data['por_igreja']), 2)
        self.assertEqual(response.data['por_turma'], [])
        self.assertEqual(response.data['summary']['total'], 150.0)
        nomes = {item['nome'] for item in response.data['por_igreja']}
        self.assertIn('Igreja Alpha', nomes)
        self.assertIn('Igreja Beta', nomes)

    def test_resumo_igreja_returns_por_turma(self):
        self._auth(self.igreja_a.id)
        response = self.client.get('/api/v1/finance/resumo/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scope'], 'igreja')
        self.assertEqual(response.data['por_igreja'], [])
        self.assertGreaterEqual(len(response.data['por_turma']), 1)
        self.assertEqual(response.data['summary']['total'], 100.0)
        adultos = next(item for item in response.data['por_turma'] if item['nome'] == 'Adultos')
        self.assertEqual(adultos['valor'], 100.0)

    def test_offerings_post_blocked_on_campo_context(self):
        self._auth(self.campo.id)
        response = self.client.post(
            '/api/v1/offerings/',
            {
                'data': '2026-03-15',
                'valor': '10.00',
                'class_group': self.turma_a.id,
                'lesson': self.lesson_a.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resumo_filter_by_class_id(self):
        self._auth(self.igreja_a.id)
        response = self.client.get(f'/api/v1/finance/resumo/?class_id={self.turma_a.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['total'], 100.0)

    def test_lancamentos_paginacao(self):
        self._auth(self.campo.id)
        response = self.client.get('/api/v1/finance/lancamentos/?page=1&page_size=1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pag = response.data['paginacao']
        self.assertEqual(pag['total'], 2)
        self.assertEqual(pag['page_size'], 1)
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(pag['total_pages'], 2)
