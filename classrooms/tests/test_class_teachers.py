from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from classrooms.models import ClassGroup, ClassTeacher
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership


class ClassTeacherApiTests(APITestCase):
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
        self.turma = ClassGroup.objects.create(
            organization=self.igreja,
            nome='Adultos',
            faixa_etaria='Adultos',
            cor='#3B82F6',
            ativa=True,
        )

        self.secretaria = User.objects.create_user(
            email='sec@test.com',
            password='123456',
            nome='Secretaria',
        )
        OrganizationMembership.objects.create(user=self.secretaria, organization=self.igreja, ativo=True)
        role_sec = Role.objects.create(nome='SECRETARIO_IGREJA')
        for module in ('turmas', 'usuarios'):
            permission = ModulePermission.objects.create(
                modulo=module,
                visualizar=True,
                criar=True,
                editar=True,
                excluir=True,
                aprovar=True,
            )
            RolePermission.objects.create(role=role_sec, permission=permission)
        UserRole.objects.create(user=self.secretaria, role=role_sec, organization=self.igreja, ativo=True)

        self.professor_a = User.objects.create_user(
            email='prof.a@test.com',
            password='123456',
            nome='Professor A',
        )
        self.professor_b = User.objects.create_user(
            email='prof.b@test.com',
            password='123456',
            nome='Professor B',
        )
        role_prof = Role.objects.create(nome='PROFESSOR')
        for professor in (self.professor_a, self.professor_b):
            OrganizationMembership.objects.create(user=professor, organization=self.igreja, ativo=True)
            UserRole.objects.create(user=professor, role=role_prof, organization=self.igreja, ativo=True)

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'sec@test.com', 'password': '123456'},
            format='json',
        )
        self.token = login.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
            HTTP_X_ORGANIZATION_ID=str(self.igreja.id),
        )

    def test_adicionar_professor_a_turma(self):
        response = self.client.post(
            '/api/v1/class-teachers/',
            {'class_group': self.turma.id, 'user': self.professor_a.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            ClassTeacher.objects.filter(class_group=self.turma, user=self.professor_a).exists()
        )

    def test_nao_permite_duplicar_professor_na_turma(self):
        ClassTeacher.objects.create(class_group=self.turma, user=self.professor_a)
        response = self.client.post(
            '/api/v1/class-teachers/',
            {'class_group': self.turma.id, 'user': self.professor_a.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remover_professor_da_turma(self):
        link = ClassTeacher.objects.create(class_group=self.turma, user=self.professor_a)
        response = self.client.delete(f'/api/v1/class-teachers/{link.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ClassTeacher.objects.filter(id=link.id).exists())

    def test_turma_pode_ter_varios_professores(self):
        ClassTeacher.objects.create(class_group=self.turma, user=self.professor_a)
        response = self.client.post(
            '/api/v1/class-teachers/',
            {'class_group': self.turma.id, 'user': self.professor_b.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ClassTeacher.objects.filter(class_group=self.turma).count(), 2)

    def test_permite_professor_em_duas_turmas(self):
        turma_b = ClassGroup.objects.create(
            organization=self.igreja,
            nome='Jovens',
            faixa_etaria='Jovens',
            cor='#22C55E',
            ativa=True,
        )
        ClassTeacher.objects.create(class_group=self.turma, user=self.professor_a)
        response = self.client.post(
            '/api/v1/class-teachers/',
            {'class_group': turma_b.id, 'user': self.professor_a.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            ClassTeacher.objects.filter(user=self.professor_a).count(),
            2,
        )


class ClassTeacherValidationTests(TestCase):
    def setUp(self):
        self.igreja = Organization.objects.create(
            nome='Igreja',
            sigla='IG',
            tipo=TIPO_IGREJA,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.turma = ClassGroup.objects.create(
            organization=self.igreja,
            nome='Jovens',
            faixa_etaria='Jovens',
            cor='#000',
            ativa=True,
        )
        self.usuario = User.objects.create_user(
            email='nao.prof@test.com',
            password='123456',
            nome='Nao Professor',
        )
        OrganizationMembership.objects.create(user=self.usuario, organization=self.igreja, ativo=True)

    def test_nao_vincula_usuario_sem_papel_professor(self):
        from classrooms.serializers import ClassTeacherSerializer

        serializer = ClassTeacherSerializer(
            data={'class_group': self.turma.id, 'user': self.usuario.id},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('user', serializer.errors)

    def test_vincula_professor_ja_em_outra_turma(self):
        from classrooms.models import ClassGroup
        from classrooms.serializers import ClassTeacherSerializer

        turma_outra = ClassGroup.objects.create(
            organization=self.igreja,
            nome='Adultos',
            faixa_etaria='Adultos',
            cor='#111',
            ativa=True,
        )
        professor = User.objects.create_user(
            email='prof.duplo@test.com',
            password='123456',
            nome='Professor Duplo',
        )
        role_professor = Role.objects.create(nome='PROFESSOR')
        UserRole.objects.create(
            user=professor,
            role=role_professor,
            organization=self.igreja,
            ativo=True,
        )
        ClassTeacher.objects.create(class_group=turma_outra, user=professor)

        serializer = ClassTeacherSerializer(
            data={'class_group': self.turma.id, 'user': professor.id},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
