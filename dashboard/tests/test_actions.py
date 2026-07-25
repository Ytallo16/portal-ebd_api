from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from attendance.models import AttendanceSheet
from classrooms.models import ClassGroup, ClassTeacher
from lessons.models import Lesson, Trimester
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership


class DashboardActionsTests(APITestCase):
    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo Ações',
            sigla='CA',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.igreja = Organization.objects.create(
            nome='Igreja Ações',
            sigla='IA',
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
            cor='#125A94',
            ativa=True,
        )
        self.trimestre = Trimester.objects.create(
            organization=self.igreja,
            numero=1,
            ano=timezone.localdate().year,
            titulo='Trimestre atual',
            status='EM_ANDAMENTO',
        )
        self.lesson = Lesson.objects.create(
            organization=self.igreja,
            numero=1,
            tema='Lição de hoje',
            data=timezone.localdate(),
            revista='Adultos',
            trimestre=self.trimestre.numero,
            ano=self.trimestre.ano,
        )

        dashboard_permission = ModulePermission.objects.create(
            modulo='dashboard',
            visualizar=True,
        )
        self.role_secretary = Role.objects.create(nome='SECRETARIO_IGREJA')
        self.role_professor = Role.objects.create(nome='PROFESSOR')
        RolePermission.objects.create(
            role=self.role_secretary,
            permission=dashboard_permission,
        )
        RolePermission.objects.create(
            role=self.role_professor,
            permission=dashboard_permission,
        )

    def _login(self, user, organization):
        response = self.client.post(
            '/api/v1/auth/login',
            {'email': user.email, 'password': '123456'},
            format='json',
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}',
            HTTP_X_ORGANIZATION_ID=str(organization.id),
        )

    def _create_user(self, email, role):
        user = User.objects.create_user(
            email=email,
            password='123456',
            nome=email.split('@')[0],
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=self.igreja,
            ativo=True,
        )
        UserRole.objects.create(
            user=user,
            role=role,
            organization=self.igreja,
            ativo=True,
        )
        return user

    def test_secretary_receives_clickable_attendance_pending_action(self):
        secretary = self._create_user('secretary@actions.test', self.role_secretary)
        self._login(secretary, self.igreja)

        response = self.client.get('/api/v1/dashboard/actions')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lesson_actions = [
            item
            for item in response.data['results']
            if item['kind'] == 'ATTENDANCE_PENDING'
        ]
        self.assertEqual(len(lesson_actions), 1)
        self.assertEqual(lesson_actions[0]['organization_id'], self.igreja.id)
        self.assertIn('/licoes/', lesson_actions[0]['action_path'])

    def test_secretary_receives_finalize_action_after_all_calls_complete(self):
        secretary = self._create_user(
            'secretary-ready@actions.test',
            self.role_secretary,
        )
        AttendanceSheet.objects.create(
            lesson=self.lesson,
            class_group=self.turma,
            finalized_at=timezone.now(),
        )
        self._login(secretary, self.igreja)

        response = self.client.get('/api/v1/dashboard/actions')

        lesson_actions = [
            item
            for item in response.data['results']
            if (
                item['kind'] == 'LESSON_FINALIZE'
                and item['metadata'].get('lesson_id') == self.lesson.id
            )
        ]
        self.assertEqual(len(lesson_actions), 1)
        self.assertEqual(
            lesson_actions[0]['metadata']['turmas_pendentes'],
            [],
        )

    def test_professor_sees_today_for_each_linked_class_without_schedule(self):
        professor = self._create_user('professor@actions.test', self.role_professor)
        turma_jovens = ClassGroup.objects.create(
            organization=self.igreja,
            nome='Jovens',
            faixa_etaria='Jovens',
            cor='#0C7A43',
            ativa=True,
        )
        ClassTeacher.objects.create(class_group=self.turma, user=professor)
        ClassTeacher.objects.create(class_group=turma_jovens, user=professor)
        self._login(professor, self.igreja)

        response = self.client.get('/api/v1/dashboard/actions')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        today_actions = [
            item
            for item in response.data['results']
            if item['kind'] == 'LESSON_TODAY'
        ]
        self.assertEqual(len(today_actions), 2)
        self.assertEqual(
            {item['metadata']['class_id'] for item in today_actions},
            {self.turma.id, turma_jovens.id},
        )

    def test_field_context_summarizes_each_church(self):
        second_church = Organization.objects.create(
            nome='Segunda Igreja',
            sigla='SI',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        second_class = ClassGroup.objects.create(
            organization=second_church,
            nome='Adultos',
            faixa_etaria='Adultos',
            cor='#333',
            ativa=True,
        )
        second_trimester = Trimester.objects.create(
            organization=second_church,
            numero=1,
            ano=timezone.localdate().year,
            titulo='Trimestre atual',
            status='EM_ANDAMENTO',
        )
        Lesson.objects.create(
            organization=second_church,
            numero=1,
            tema='Lição anterior',
            data=timezone.localdate() - timedelta(days=7),
            revista='Adultos',
            trimestre=second_trimester.numero,
            ano=second_trimester.ano,
        )
        self.assertIsNotNone(second_class.id)

        admin = User.objects.create_superuser(
            email='admin@actions.test',
            password='123456',
            nome='Admin',
        )
        self._login(admin, self.campo)

        response = self.client.get('/api/v1/dashboard/actions')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        summaries = response.data['summary_by_organization']
        self.assertEqual(
            {item['organization_id'] for item in summaries},
            {self.igreja.id, second_church.id},
        )
