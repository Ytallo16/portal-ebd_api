from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from classrooms.models import ClassGroup, ClassTeacher
from lessons.models import Trimester
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership
from publications.models import PublicationControl
from publications.services import sync_publication_controls
from students.models import Student


class PublicationControlServiceTests(TestCase):
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
        self.igreja = Organization.objects.create(
            nome='Igreja Teste',
            sigla='IT',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.trimester = Trimester.objects.create(
            organization=self.igreja,
            numero=1,
            ano=2026,
            titulo='1º Trimestre 2026',
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 31),
            status='EM_ANDAMENTO',
        )
        self.turma = ClassGroup.objects.create(
            organization=self.igreja,
            nome='Adultos',
            faixa_etaria='Adultos',
            cor='#3B82F6',
            ativa=True,
        )
        self.professor = User.objects.create_user(
            email='prof@test.com',
            password='123456',
            nome='Professor Teste',
        )
        ClassTeacher.objects.create(class_group=self.turma, user=self.professor)
        self.aluno = Student.objects.create(
            organization=self.igreja,
            class_group=self.turma,
            nome='Aluno Teste',
            sexo='M',
            data_nascimento=date(2010, 1, 1),
            ativo=True,
        )

    def test_sync_cria_controles_para_aluno_e_professor(self):
        created = sync_publication_controls(self.igreja, self.trimester)
        self.assertEqual(created, 2)
        self.assertEqual(PublicationControl.objects.filter(trimester=self.trimester).count(), 2)

    def test_sync_nao_duplica_registros(self):
        sync_publication_controls(self.igreja, self.trimester)
        created = sync_publication_controls(self.igreja, self.trimester)
        self.assertEqual(created, 0)
        self.assertEqual(PublicationControl.objects.filter(trimester=self.trimester).count(), 2)

    def test_sync_preserva_flags_existentes(self):
        sync_publication_controls(self.igreja, self.trimester)
        control = PublicationControl.objects.get(student=self.aluno, trimester=self.trimester)
        control.recebeu = True
        control.pagou = True
        control.save(update_fields=['recebeu', 'pagou'])

        sync_publication_controls(self.igreja, self.trimester)
        control.refresh_from_db()
        self.assertTrue(control.recebeu)
        self.assertTrue(control.pagou)


class PublicationControlApiTests(APITestCase):
    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo API',
            sigla='CA',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.igreja = Organization.objects.create(
            nome='Igreja API',
            sigla='IA',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.outra_igreja = Organization.objects.create(
            nome='Igreja Outra',
            sigla='IO',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.trimester = Trimester.objects.create(
            organization=self.igreja,
            numero=1,
            ano=2026,
            titulo='1º Trimestre 2026',
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 31),
            status='EM_ANDAMENTO',
        )
        self.outro_trimestre = Trimester.objects.create(
            organization=self.outra_igreja,
            numero=1,
            ano=2026,
            titulo='1º Trimestre 2026',
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 31),
            status='EM_ANDAMENTO',
        )
        self.turma = ClassGroup.objects.create(
            organization=self.igreja,
            nome='Jovens',
            faixa_etaria='Jovens',
            cor='#10B981',
            ativa=True,
        )
        self.professor = User.objects.create_user(
            email='sec.igreja@test.com',
            password='123456',
            nome='Secretaria Igreja',
        )
        OrganizationMembership.objects.create(user=self.professor, organization=self.igreja, ativo=True)
        role = Role.objects.create(nome='SECRETARIO_IGREJA')
        permission = ModulePermission.objects.create(
            modulo='revistas',
            visualizar=True,
            criar=True,
            editar=True,
            excluir=False,
            aprovar=True,
        )
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(user=self.professor, role=role, organization=self.igreja, ativo=True)

        self.aluno = Student.objects.create(
            organization=self.igreja,
            class_group=self.turma,
            nome='Maria Silva',
            sexo='F',
            data_nascimento=date(2012, 5, 10),
            ativo=True,
        )
        self.control = PublicationControl.objects.create(
            organization=self.igreja,
            trimester=self.trimester,
            class_group=self.turma,
            person_type='aluno',
            person_name=self.aluno.nome,
            student=self.aluno,
            recebeu=False,
            pagou=False,
        )
        PublicationControl.objects.create(
            organization=self.outra_igreja,
            trimester=self.outro_trimestre,
            class_group=ClassGroup.objects.create(
                organization=self.outra_igreja,
                nome='Adultos',
                faixa_etaria='Adultos',
                cor='#000000',
                ativa=True,
            ),
            person_type='aluno',
            person_name='Externo',
            recebeu=True,
            pagou=True,
        )

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'sec.igreja@test.com', 'password': '123456'},
            format='json',
        )
        self.token = login.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
            HTTP_X_ORGANIZATION_ID=str(self.igreja.id),
        )

    def test_lista_filtra_por_trimestre(self):
        response = self.client.get(
            f'/api/v1/publication-controls/?trimester_id={self.trimester.id}',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.control.id)

    def test_nao_vaza_dados_de_outra_igreja(self):
        response = self.client.get('/api/v1/publication-controls/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['person_name'], 'Maria Silva')

    def test_sync_cria_novos_controles(self):
        professor = User.objects.create_user(email='prof2@test.com', password='123456', nome='Prof 2')
        ClassTeacher.objects.create(class_group=self.turma, user=professor)

        response = self.client.post(
            '/api/v1/publication-controls/sync/',
            {'trimester_id': self.trimester.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['created_count'], 1)
        self.assertEqual(response.data['total_count'], 2)

    def test_bulk_toggle_marca_recebeu(self):
        response = self.client.patch(
            '/api/v1/publication-controls/bulk-toggle/',
            {
                'trimester_id': self.trimester.id,
                'class_id': self.turma.id,
                'person_type': 'aluno',
                'field': 'recebeu',
                'value': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated_count'], 1)
        self.control.refresh_from_db()
        self.assertTrue(self.control.recebeu)

    def test_toggle_unitario(self):
        response = self.client.patch(
            f'/api/v1/publication-controls/{self.control.id}/toggle/',
            {'recebeu': True, 'pagou': True, 'metodo_pagamento': 'PIX'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.control.refresh_from_db()
        self.assertTrue(self.control.recebeu)
        self.assertTrue(self.control.pagou)
        self.assertEqual(self.control.metodo_pagamento, 'PIX')
