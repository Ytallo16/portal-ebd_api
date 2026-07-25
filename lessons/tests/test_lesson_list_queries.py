from datetime import date, timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from access_control.constants import ROLE_SECRETARIO_IGREJA
from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from attendance.models import AttendanceRecord, AttendanceSheet
from classrooms.models import ClassGroup
from lessons.models import Lesson
from organizations.constants import TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership
from students.models import Student


class LessonListQueryTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            nome='Igreja Consultas',
            sigla='ICQ',
            tipo=TIPO_IGREJA,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.turma = ClassGroup.objects.create(
            organization=self.org,
            nome='Adultos',
            faixa_etaria='Adultos',
            cor='#123456',
            ativa=True,
        )
        self.presente = Student.objects.create(
            organization=self.org,
            class_group=self.turma,
            nome='Aluno Presente',
            sexo='M',
            data_nascimento=date(2000, 1, 1),
            ativo=True,
        )
        self.ausente = Student.objects.create(
            organization=self.org,
            class_group=self.turma,
            nome='Aluno Ausente',
            sexo='F',
            data_nascimento=date(2000, 2, 1),
            ativo=True,
        )

        self.secretario = User.objects.create_user(
            email='secretario.consultas@teste.com',
            password='123456',
            nome='Secretário',
        )
        OrganizationMembership.objects.create(
            user=self.secretario,
            organization=self.org,
            ativo=True,
        )
        role = Role.objects.create(nome=ROLE_SECRETARIO_IGREJA)
        for module in ('licoes', 'turmas'):
            permission = ModulePermission.objects.create(
                modulo=module,
                visualizar=True,
            )
            RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(
            user=self.secretario,
            role=role,
            organization=self.org,
            ativo=True,
        )

        self.client.force_authenticate(user=self.secretario)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        self.first_lesson = self._create_lesson_with_attendance(1)

    def _create_lesson_with_attendance(self, numero):
        lesson = Lesson.objects.create(
            organization=self.org,
            numero=numero,
            tema=f'Lição {numero}',
            data=date(2026, 1, 1) + timedelta(days=numero),
            revista='Adultos',
            trimestre=1,
            ano=2026,
        )
        sheet = AttendanceSheet.objects.create(
            lesson=lesson,
            class_group=self.turma,
        )
        AttendanceRecord.objects.create(
            attendance_sheet=sheet,
            student=self.presente,
            presente=True,
        )
        AttendanceRecord.objects.create(
            attendance_sheet=sheet,
            student=self.ausente,
            presente=False,
        )
        return lesson

    def _request_with_query_count(self, url):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        return response, len(queries)

    def test_lesson_list_returns_attendance_totals_without_query_growth(self):
        first_response, first_query_count = self._request_with_query_count(
            '/api/v1/lessons/?ano=2026&trimestre=1'
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        first_results = first_response.data['results']
        self.assertEqual(first_results[0]['presentes'], 1)
        self.assertEqual(first_results[0]['ausentes'], 1)

        for numero in range(2, 11):
            self._create_lesson_with_attendance(numero)

        many_response, many_query_count = self._request_with_query_count(
            '/api/v1/lessons/?ano=2026&trimestre=1'
        )
        self.assertEqual(many_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(many_response.data['results']), 10)
        self.assertTrue(
            all(item['presentes'] == 1 for item in many_response.data['results'])
        )
        self.assertTrue(
            all(item['ausentes'] == 1 for item in many_response.data['results'])
        )
        self.assertLessEqual(many_query_count, first_query_count + 1)

    def test_class_lesson_list_uses_the_same_aggregated_totals(self):
        url = f'/api/v1/classes/{self.turma.id}/lessons/?ano=2026&trimestre=1'
        first_response, first_query_count = self._request_with_query_count(url)
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(first_response.data[0]['presentes'], 1)
        self.assertEqual(first_response.data[0]['ausentes'], 1)

        for numero in range(2, 8):
            self._create_lesson_with_attendance(numero)

        response, query_count = self._request_with_query_count(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 7)
        self.assertTrue(all(item['presentes'] == 1 for item in response.data))
        self.assertTrue(all(item['ausentes'] == 1 for item in response.data))
        self.assertLessEqual(query_count, first_query_count + 1)
