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
from classrooms.models import ClassGroup, ClassTeacher
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership


class UserRoleUpdateApiTests(APITestCase):
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

        self.role_admin = Role.objects.create(nome=ROLE_ADMINISTRADOR)
        self.role_campo = Role.objects.create(nome=ROLE_SECRETARIO_CAMPO)
        self.role_igreja = Role.objects.create(nome=ROLE_SECRETARIO_IGREJA)
        self.role_professor = Role.objects.create(nome=ROLE_PROFESSOR)

        for module in ('turmas', 'usuarios'):
            permission = ModulePermission.objects.create(
                modulo=module,
                visualizar=True,
                criar=True,
                editar=True,
                excluir=True,
                aprovar=True,
            )
            RolePermission.objects.create(role=self.role_igreja, permission=permission)
            RolePermission.objects.create(role=self.role_campo, permission=permission)

        self.secretaria = User.objects.create_user(
            email='sec@test.com',
            password='123456',
            nome='Secretaria',
        )
        OrganizationMembership.objects.create(user=self.secretaria, organization=self.igreja, ativo=True)
        UserRole.objects.create(
            user=self.secretaria,
            role=self.role_igreja,
            organization=self.igreja,
            ativo=True,
        )

        self.professor = User.objects.create_user(
            email='prof@test.com',
            password='123456',
            nome='Professor',
        )
        OrganizationMembership.objects.create(user=self.professor, organization=self.igreja, ativo=True)
        UserRole.objects.create(
            user=self.professor,
            role=self.role_professor,
            organization=self.igreja,
            ativo=True,
        )

        self.autenticar(self.secretaria)

    def autenticar(self, user, organization=None):
        login = self.client.post(
            '/api/v1/auth/login',
            {'email': user.email, 'password': '123456'},
            format='json',
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}',
            HTTP_X_ORGANIZATION_ID=str((organization or self.igreja).id),
        )

    def papeis_ativos(self, user):
        return set(
            UserRole.objects.filter(user=user, ativo=True)
            .select_related('role')
            .values_list('role__nome', flat=True)
        )

    def test_atualiza_papel_do_usuario(self):
        response = self.client.patch(
            f'/api/v1/users/{self.professor.id}/',
            {'papel': ROLE_SECRETARIO_IGREJA},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.papeis_ativos(self.professor), {ROLE_SECRETARIO_IGREJA})
        self.assertEqual(response.data['papeis'], [ROLE_SECRETARIO_IGREJA])

        membership = OrganizationMembership.objects.get(user=self.professor, organization=self.igreja)
        self.assertEqual(membership.role_scope, ROLE_SECRETARIO_IGREJA.lower())

        self.professor.refresh_from_db()
        self.assertTrue(self.professor.is_staff)

    def test_deixar_de_ser_professor_remove_vinculo_com_turma(self):
        ClassTeacher.objects.create(class_group=self.turma, user=self.professor)

        response = self.client.patch(
            f'/api/v1/users/{self.professor.id}/',
            {'papel': ROLE_SECRETARIO_IGREJA},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ClassTeacher.objects.filter(user=self.professor).exists())

    def test_manter_papel_professor_preserva_vinculo(self):
        ClassTeacher.objects.create(class_group=self.turma, user=self.professor)

        response = self.client.patch(
            f'/api/v1/users/{self.professor.id}/',
            {'nome': 'Professor Editado', 'papel': ROLE_PROFESSOR},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(ClassTeacher.objects.filter(user=self.professor).exists())

    def test_secretario_de_igreja_nao_concede_papel_de_administrador(self):
        response = self.client.patch(
            f'/api/v1/users/{self.professor.id}/',
            {'papel': ROLE_ADMINISTRADOR},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('papel', response.data)
        self.assertEqual(self.papeis_ativos(self.professor), {ROLE_PROFESSOR})

    def test_secretario_de_igreja_nao_concede_papel_de_campo(self):
        response = self.client.patch(
            f'/api/v1/users/{self.professor.id}/',
            {'papel': ROLE_SECRETARIO_CAMPO},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('papel', response.data)

    def test_nao_permite_alterar_o_proprio_papel(self):
        response = self.client.patch(
            f'/api/v1/users/{self.secretaria.id}/',
            {'papel': ROLE_PROFESSOR},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.papeis_ativos(self.secretaria), {ROLE_SECRETARIO_IGREJA})

    def test_papel_de_igreja_exige_contexto_de_igreja(self):
        UserRole.objects.create(
            user=self.secretaria,
            role=self.role_campo,
            organization=self.campo,
            ativo=True,
        )
        OrganizationMembership.objects.create(user=self.secretaria, organization=self.campo, ativo=True)
        self.autenticar(self.secretaria, organization=self.campo)

        response = self.client.patch(
            f'/api/v1/users/{self.professor.id}/',
            {'papel': ROLE_PROFESSOR},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('papel', response.data)

    def test_atualiza_dados_sem_enviar_papel(self):
        response = self.client.patch(
            f'/api/v1/users/{self.professor.id}/',
            {'nome': 'Professor Renomeado', 'email': 'novo@test.com', 'is_active': False},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.professor.refresh_from_db()
        self.assertEqual(self.professor.nome, 'Professor Renomeado')
        self.assertEqual(self.professor.email, 'novo@test.com')
        self.assertFalse(self.professor.is_active)
        self.assertEqual(self.papeis_ativos(self.professor), {ROLE_PROFESSOR})
