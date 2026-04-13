from datetime import date, timedelta

from django.test import TestCase

from access_control.models import Role, UserRole
from accounts.models import User
from lessons.services import can_edit_lesson
from organizations.models import Organization


class LessonPermissionServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            nome='Org', sigla='OG', tipo='SEDE', cidade='Teresina', uf='PI', status='ATIVA'
        )

    def _build_user_with_role(self, email, role_name):
        user = User.objects.create_user(email=email, password='123456', nome=role_name)
        role = Role.objects.create(nome=role_name)
        UserRole.objects.create(user=user, role=role, organization=self.org, ativo=True)
        return user

    def test_professor_can_edit_only_on_lesson_day(self):
        professor = self._build_user_with_role('prof@test.com', 'PROFESSOR')

        class LessonStub:
            def __init__(self, lesson_date):
                self.data = lesson_date

        self.assertTrue(can_edit_lesson(professor, LessonStub(date.today())))
        self.assertFalse(can_edit_lesson(professor, LessonStub(date.today() - timedelta(days=1))))

    def test_admin_can_always_edit(self):
        admin = self._build_user_with_role('admin2@test.com', 'ADMINISTRADOR')

        class LessonStub:
            def __init__(self, lesson_date):
                self.data = lesson_date

        self.assertTrue(can_edit_lesson(admin, LessonStub(date.today() - timedelta(days=10))))
        self.assertTrue(can_edit_lesson(admin, LessonStub(date.today() + timedelta(days=5))))
