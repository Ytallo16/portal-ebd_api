from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from classrooms.models import ClassGroup, ClassTeacher
from core.scoping import can_access_organization, get_accessible_organization_ids, get_org_descendant_ids
from lessons.models import Lesson
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership
from students.models import Student


class OrganizationScopingTests(TestCase):
    def setUp(self):
        self.campo_a = Organization.objects.create(
            nome='Campo A', sigla='CA', tipo=TIPO_CAMPO, formato=FORMATO_CAMPO, cidade='Teresina', uf='PI', status='ATIVA'
        )
        self.igreja_a = Organization.objects.create(
            nome='Igreja A',
            sigla='IA',
            tipo=TIPO_IGREJA,
            parent=self.campo_a,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.campo_b = Organization.objects.create(
            nome='Campo B', sigla='CB', tipo=TIPO_CAMPO, formato=FORMATO_CAMPO, cidade='Parnaíba', uf='PI', status='ATIVA'
        )
        self.igreja_b = Organization.objects.create(
            nome='Igreja B',
            sigla='IB',
            tipo=TIPO_IGREJA,
            parent=self.campo_b,
            cidade='Parnaíba',
            uf='PI',
            status='ATIVA',
        )

    def test_descendants_include_campo_and_children(self):
        ids = get_org_descendant_ids(self.campo_a)
        self.assertIn(self.campo_a.id, ids)
        self.assertIn(self.igreja_a.id, ids)
        self.assertNotIn(self.igreja_b.id, ids)

    def test_secretario_campo_accessible_orgs(self):
        user = User.objects.create_user(email='sec.campo@test.com', password='123456', nome='Sec Campo')
        role = Role.objects.create(nome='SECRETARIO_CAMPO')
        UserRole.objects.create(user=user, role=role, organization=self.campo_a, ativo=True)

        accessible = set(get_accessible_organization_ids(user))
        self.assertEqual(accessible, {self.campo_a.id, self.igreja_a.id})
        self.assertTrue(can_access_organization(user, self.igreja_a.id))
        self.assertFalse(can_access_organization(user, self.igreja_b.id))


class TenantIsolationApiTests(APITestCase):
    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo Teste', sigla='CT', tipo=TIPO_CAMPO, formato=FORMATO_CAMPO, cidade='Teresina', uf='PI', status='ATIVA'
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
        self.outra_igreja = Organization.objects.create(
            nome='Igreja Outra',
            sigla='IO',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )

        self.user = User.objects.create_user(email='sec.igreja@test.com', password='123456', nome='Secretaria')
        OrganizationMembership.objects.create(user=self.user, organization=self.igreja, ativo=True)
        role = Role.objects.create(nome='SECRETARIO_IGREJA')
        for module in ('licoes', 'alunos', 'turmas', 'dashboard'):
            permission = ModulePermission.objects.create(
                modulo=module, visualizar=True, criar=True, editar=True, excluir=True, aprovar=True
            )
            RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(user=self.user, role=role, organization=self.igreja, ativo=True)

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

        Lesson.objects.create(
            organization=self.igreja,
            numero=1,
            tema='Lição local',
            data=date.today(),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )
        Lesson.objects.create(
            organization=self.outra_igreja,
            numero=1,
            tema='Lição externa',
            data=date.today(),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )

    def test_lessons_scoped_to_active_church(self):
        response = self.client.get('/api/v1/lessons/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['tema'], 'Lição local')

    def test_cannot_access_other_church_with_header(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
            HTTP_X_ORGANIZATION_ID=str(self.outra_igreja.id),
        )
        response = self.client.get('/api/v1/lessons/')
        self.assertIn(response.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))


class ProfessorScopeTests(APITestCase):
    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo Prof', sigla='CP', tipo=TIPO_CAMPO, formato=FORMATO_CAMPO, cidade='Teresina', uf='PI', status='ATIVA'
        )
        self.igreja = Organization.objects.create(
            nome='Igreja Prof',
            sigla='IP',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.turma_a = ClassGroup.objects.create(
            organization=self.igreja, nome='Adultos', faixa_etaria='Adultos', cor='#000', ativa=True
        )
        self.turma_b = ClassGroup.objects.create(
            organization=self.igreja, nome='Jovens', faixa_etaria='Jovens', cor='#111', ativa=True
        )

        self.professor = User.objects.create_user(email='prof@test.com', password='123456', nome='Professor')
        OrganizationMembership.objects.create(user=self.professor, organization=self.igreja, ativo=True)
        role = Role.objects.create(nome='PROFESSOR')
        for module in ('alunos', 'turmas', 'licoes', 'frequencia', 'dashboard'):
            permission = ModulePermission.objects.create(
                modulo=module, visualizar=True, criar=True, editar=True, excluir=False, aprovar=False
            )
            RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(user=self.professor, role=role, organization=self.igreja, ativo=True)
        ClassTeacher.objects.create(class_group=self.turma_a, user=self.professor)

        Student.objects.create(
            organization=self.igreja,
            class_group=self.turma_a,
            nome='Aluno Turma A',
            sexo='M',
            data_nascimento=date(2000, 1, 1),
            email='a@test.com',
            telefone='86999999999',
            ativo=True,
        )
        Student.objects.create(
            organization=self.igreja,
            class_group=self.turma_b,
            nome='Aluno Turma B',
            sexo='F',
            data_nascimento=date(2001, 1, 1),
            email='b@test.com',
            telefone='86999999998',
            ativo=True,
        )

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'prof@test.com', 'password': '123456'},
            format='json',
        )
        self.token = login.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
            HTTP_X_ORGANIZATION_ID=str(self.igreja.id),
        )

    def test_professor_sees_only_students_from_assigned_class(self):
        response = self.client.get('/api/v1/students/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['nome'], 'Aluno Turma A')
