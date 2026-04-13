from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from classrooms.models import ClassGroup
from lessons.models import Lesson
from organizations.models import Organization, OrganizationMembership
from students.models import Student


class AttendanceFlowTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            nome='Org Presença',
            sigla='OP',
            tipo='SEDE',
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.user = User.objects.create_user(email='coord@test.com', password='123456', nome='Coordenador')
        OrganizationMembership.objects.create(user=self.user, organization=self.org, ativo=True)

        role = Role.objects.create(nome='ADMINISTRADOR')
        for module in ['licoes', 'frequencia', 'turmas', 'alunos']:
            perm = ModulePermission.objects.create(
                modulo=module,
                visualizar=True,
                criar=True,
                editar=True,
                excluir=True,
                aprovar=True,
            )
            RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.user, role=role, organization=self.org, ativo=True)

        login = self.client.post('/api/v1/auth/login', {'email': 'coord@test.com', 'password': '123456'}, format='json')
        token = login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}', HTTP_X_ORGANIZATION_ID=str(self.org.id))

        self.class_group = ClassGroup.objects.create(
            organization=self.org,
            nome='Adultos I',
            faixa_etaria='26-35',
            cor='#125A94',
            created_by=self.user,
        )
        self.lesson = Lesson.objects.create(
            organization=self.org,
            numero=1,
            tema='Tema',
            data=date.today(),
            revista='Revista',
            trimestre=1,
            ano=2026,
            created_by=self.user,
        )
        self.student = Student.objects.create(
            organization=self.org,
            class_group=self.class_group,
            nome='Aluno 1',
            sexo='M',
            data_nascimento=date(2000, 1, 1),
            created_by=self.user,
        )

    def test_full_attendance_and_finalize_lesson_flow(self):
        create_sheet = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': self.lesson.id,
                'class_group': self.class_group.id,
                'professor': self.user.id,
                'visitantes': 1,
                'biblias': 10,
                'revistas': 8,
                'oferta_valor': '25.00',
            },
            format='json',
        )
        self.assertEqual(create_sheet.status_code, status.HTTP_201_CREATED)
        sheet_id = create_sheet.data['id']

        records = self.client.post(
            f'/api/v1/attendance-sheets/{sheet_id}/records/',
            {'records': [{'student': self.student.id, 'presente': True}], 'finalize_sheet': True},
            format='json',
        )
        self.assertEqual(records.status_code, status.HTTP_200_OK)
        self.assertEqual(len(records.data['records']), 1)
        self.assertTrue(records.data['records'][0]['presente'])

        finalize_lesson = self.client.post(f'/api/v1/lessons/{self.lesson.id}/finalize/')
        self.assertEqual(finalize_lesson.status_code, status.HTTP_200_OK)
        self.assertEqual(finalize_lesson.data['status'], 'FINALIZADA')

    def test_finalize_lesson_without_sheet_fails(self):
        response = self.client.post(f'/api/v1/lessons/{self.lesson.id}/finalize/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
