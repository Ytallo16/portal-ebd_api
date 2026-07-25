from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from attendance.models import AttendanceRecord, AttendanceSheet
from classrooms.models import ClassGroup
from lessons.models import Lesson
from organizations.constants import TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership
from students.models import Student, StudentHistory


class StudentLifecycleTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            nome='Igreja Histórico',
            sigla='IH',
            tipo=TIPO_IGREJA,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.user = User.objects.create_user(
            email='historico@test.com',
            password='123456',
            nome='Secretária',
        )
        OrganizationMembership.objects.create(
            user=self.user,
            organization=self.organization,
            ativo=True,
        )
        role = Role.objects.create(nome='SECRETARIO_IGREJA')
        permission = ModulePermission.objects.create(
            modulo='alunos',
            visualizar=True,
            criar=True,
            editar=True,
            excluir=True,
            aprovar=True,
        )
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(
            user=self.user,
            role=role,
            organization=self.organization,
            ativo=True,
        )
        self.class_group = ClassGroup.objects.create(
            organization=self.organization,
            nome='Adultos',
            faixa_etaria='18+',
        )
        self.student = Student.objects.create(
            organization=self.organization,
            class_group=self.class_group,
            nome='Aluno com histórico',
            sexo='M',
            data_nascimento=date(1990, 1, 1),
        )
        lesson = Lesson.objects.create(
            organization=self.organization,
            numero=1,
            tema='Lição',
            data=date.today(),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )
        sheet = AttendanceSheet.objects.create(
            lesson=lesson,
            class_group=self.class_group,
        )
        self.record = AttendanceRecord.objects.create(
            attendance_sheet=sheet,
            student=self.student,
            presente=True,
        )
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.organization.id))

    def test_delete_soft_deactivates_and_preserves_attendance_then_restore(self):
        response = self.client.delete(f'/api/v1/students/{self.student.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        self.assertFalse(self.student.ativo)
        self.assertIsNotNone(self.student.deleted_at)
        self.assertTrue(AttendanceRecord.objects.filter(pk=self.record.pk).exists())
        self.assertTrue(
            StudentHistory.objects.filter(
                student=self.student,
                action=StudentHistory.ACTION_DEACTIVATED,
            ).exists()
        )

        inactive = self.client.get('/api/v1/students/inactive/')
        self.assertEqual(inactive.status_code, status.HTTP_200_OK)
        self.assertEqual(inactive.data['count'], 1)

        restore = self.client.post(f'/api/v1/students/{self.student.id}/restore/')
        self.assertEqual(restore.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        self.assertTrue(self.student.ativo)
        self.assertIsNone(self.student.deleted_at)
        self.assertTrue(AttendanceRecord.objects.filter(pk=self.record.pk).exists())
        self.assertTrue(
            StudentHistory.objects.filter(
                student=self.student,
                action=StudentHistory.ACTION_RESTORED,
            ).exists()
        )

    def test_update_records_changed_fields_in_history(self):
        response = self.client.patch(
            f'/api/v1/students/{self.student.id}/',
            {'telefone': '(86) 99999-0000'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = StudentHistory.objects.get(
            student=self.student,
            action=StudentHistory.ACTION_UPDATED,
        )
        self.assertEqual(event.actor, self.user)
        self.assertEqual(
            event.changes['telefone'],
            {'antes': '', 'depois': '(86) 99999-0000'},
        )

        history = self.client.get(f'/api/v1/students/{self.student.id}/history/')
        self.assertEqual(history.status_code, status.HTTP_200_OK)
        self.assertEqual(history.data['count'], 1)
        self.assertEqual(history.data['results'][0]['action'], 'UPDATED')

    def test_student_list_searches_and_paginates_on_server(self):
        Student.objects.bulk_create(
            [
                Student(
                    organization=self.organization,
                    class_group=self.class_group,
                    nome=f'Aluno paginado {index:02d}',
                    sexo='M',
                    data_nascimento=date(2000, 1, 1),
                )
                for index in range(30)
            ]
        )

        first_page = self.client.get(
            '/api/v1/students/',
            {'search': 'paginado', 'page': 1, 'page_size': 10},
        )
        second_page = self.client.get(
            '/api/v1/students/',
            {'search': 'paginado', 'page': 2, 'page_size': 10},
        )

        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(first_page.data['count'], 30)
        self.assertEqual(len(first_page.data['results']), 10)
        self.assertEqual(len(second_page.data['results']), 10)
        self.assertNotEqual(
            first_page.data['results'][0]['id'],
            second_page.data['results'][0]['id'],
        )
