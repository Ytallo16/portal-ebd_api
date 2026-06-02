from datetime import date, timedelta

from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from attendance.models import AttendanceSheet
from classrooms.models import ClassGroup, ClassTeacher
from lessons.models import Lesson, Trimester
from notifications.models import Notification
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership
from publications.models import PublicationControl


class NotificationSyncTests(APITestCase):
    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo Notif',
            sigla='CN',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.org = Organization.objects.create(
            nome='Igreja Notif',
            sigla='IN',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.turma = ClassGroup.objects.create(
            organization=self.org,
            nome='Adultos',
            faixa_etaria='Adultos',
            cor='#125A94',
            ativa=True,
        )
        self.trimestre = Trimester.objects.create(
            organization=self.org,
            numero=1,
            ano=2026,
            titulo='1º Trimestre 2026',
            status='EM_ANDAMENTO',
        )

        today = date.today()
        self.lesson_done = Lesson.objects.create(
            organization=self.org,
            numero=1,
            tema='Lição 1',
            data=today - timedelta(days=14),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )
        self.lesson_pending = Lesson.objects.create(
            organization=self.org,
            numero=2,
            tema='Lição 2',
            data=today - timedelta(days=7),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )

        self.prof = User.objects.create_user(
            email='prof.notif@test.com',
            password='123456',
            nome='Prof Notif',
        )
        self.secretario = User.objects.create_user(
            email='sec.notif@test.com',
            password='123456',
            nome='Sec Notif',
        )

        for user in (self.prof, self.secretario):
            OrganizationMembership.objects.create(user=user, organization=self.org, ativo=True)

        role_prof = Role.objects.create(nome='PROFESSOR')
        role_sec = Role.objects.create(nome='SECRETARIO_IGREJA')
        for module in ('dashboard', 'licoes', 'frequencia', 'turmas', 'alunos', 'revistas'):
            perm = ModulePermission.objects.create(
                modulo=module,
                visualizar=True,
                criar=True,
                editar=True,
                excluir=False,
                aprovar=False,
            )
            RolePermission.objects.create(role=role_prof, permission=perm)
            RolePermission.objects.create(role=role_sec, permission=perm)

        UserRole.objects.create(user=self.prof, role=role_prof, organization=self.org, ativo=True)
        UserRole.objects.create(user=self.secretario, role=role_sec, organization=self.org, ativo=True)
        ClassTeacher.objects.create(class_group=self.turma, user=self.prof)

        AttendanceSheet.objects.create(
            lesson=self.lesson_done,
            class_group=self.turma,
            professor=self.prof,
        )

        PublicationControl.objects.create(
            organization=self.org,
            trimester=self.trimestre,
            class_group=self.turma,
            person_type='aluno',
            person_name='Aluno Revista',
            recebeu=True,
            pagou=False,
        )

    def _login(self, email):
        login = self.client.post(
            '/api/v1/auth/login',
            {'email': email, 'password': '123456'},
            format='json',
        )
        token = login.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token}',
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

    def test_professor_sync_creates_attendance_pending(self):
        self._login('prof.notif@test.com')
        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['unread_count'], 1)
        kinds = {item['kind'] for item in response.data['results']}
        self.assertIn('ATTENDANCE_PENDING', kinds)
        dedupe = f'attendance:lesson:{self.lesson_pending.id}:class:{self.turma.id}'
        self.assertTrue(
            Notification.objects.filter(
                user=self.prof,
                organization=self.org,
                dedupe_key=dedupe,
            ).exists()
        )

    def test_sheet_created_removes_attendance_notification(self):
        self._login('prof.notif@test.com')
        self.client.get('/api/v1/notifications/')
        dedupe = f'attendance:lesson:{self.lesson_pending.id}:class:{self.turma.id}'
        self.assertTrue(
            Notification.objects.filter(user=self.prof, dedupe_key=dedupe).exists()
        )

        AttendanceSheet.objects.create(
            lesson=self.lesson_pending,
            class_group=self.turma,
            professor=self.prof,
        )
        self.client.get('/api/v1/notifications/')
        self.assertFalse(
            Notification.objects.filter(user=self.prof, dedupe_key=dedupe).exists()
        )

    def test_read_preserves_on_resync(self):
        self._login('prof.notif@test.com')
        self.client.get('/api/v1/notifications/')
        notification = Notification.objects.filter(user=self.prof).first()
        self.assertIsNotNone(notification)

        read_response = self.client.patch(f'/api/v1/notifications/{notification.id}/read/')
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)

        list_after_read = self.client.get('/api/v1/notifications/')
        self.assertEqual(list_after_read.data['results'], [])
        self.assertEqual(list_after_read.data['unread_count'], 0)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)

    def test_read_all_hides_notifications_on_next_list(self):
        self._login('sec.notif@test.com')
        first = self.client.get('/api/v1/notifications/')
        self.assertGreater(len(first.data['results']), 0)

        self.client.post('/api/v1/notifications/read-all/')
        second = self.client.get('/api/v1/notifications/')
        self.assertEqual(second.data['results'], [])
        self.assertEqual(second.data['unread_count'], 0)

    def test_secretary_gets_magazine_payment_notification(self):
        self._login('sec.notif@test.com')
        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        kinds = {item['kind'] for item in response.data['results']}
        self.assertIn('MAGAZINE_PAYMENT', kinds)
        self.assertIn('LESSON_FINALIZE', kinds)

    def test_read_all_marks_notifications(self):
        self._login('sec.notif@test.com')
        self.client.get('/api/v1/notifications/')
        response = self.client.post('/api/v1/notifications/read-all/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 0)
        self.assertFalse(
            Notification.objects.filter(
                user=self.secretario,
                organization=self.org,
                read_at__isnull=True,
            ).exists()
        )

    def test_mark_read_decrements_unread_count(self):
        self._login('prof.notif@test.com')
        list_response = self.client.get('/api/v1/notifications/')
        initial_unread = list_response.data['unread_count']
        notification_id = list_response.data['results'][0]['id']

        read_response = self.client.patch(f'/api/v1/notifications/{notification_id}/read/')
        self.assertEqual(read_response.data['unread_count'], initial_unread - 1)
        self.assertTrue(read_response.data['notification']['read'])

        list_after = self.client.get('/api/v1/notifications/')
        ids = {item['id'] for item in list_after.data['results']}
        self.assertNotIn(notification_id, ids)
