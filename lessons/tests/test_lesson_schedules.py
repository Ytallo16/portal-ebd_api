from datetime import date

from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from classrooms.models import ClassGroup, ClassTeacher
from lessons.models import Lesson, LessonSchedule, Trimester
from organizations.constants import TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership


class LessonScheduleApiTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            nome='Igreja Escala',
            sigla='IE',
            tipo=TIPO_IGREJA,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.turma = ClassGroup.objects.create(
            organization=self.org,
            nome='Adultos',
            faixa_etaria='Adultos',
            cor='#000',
            ativa=True,
        )
        self.trimestre = Trimester.objects.create(
            organization=self.org,
            numero=1,
            ano=2026,
            status='EM_ANDAMENTO',
        )
        self.lesson = Lesson.objects.create(
            organization=self.org,
            numero=1,
            tema='A fé de Abraão',
            data=date(2026, 1, 11),
            revista='Adultos',
            trimestre=1,
            ano=2026,
        )
        self.secretario = User.objects.create_user(
            email='sec.escala@test.com',
            password='123456',
            nome='Secretaria',
            is_staff=True,
        )
        self.professor = User.objects.create_user(
            email='prof.escala@test.com',
            password='123456',
            nome='Professor Escala',
        )
        for user in (self.secretario, self.professor):
            OrganizationMembership.objects.create(user=user, organization=self.org, ativo=True)

        role_sec = Role.objects.create(nome='SECRETARIO_IGREJA')
        role_prof = Role.objects.create(nome='PROFESSOR')
        for module in ('licoes', 'frequencia', 'dashboard'):
            perm = ModulePermission.objects.create(
                modulo=module,
                visualizar=True,
                criar=True,
                editar=True,
                excluir=False,
                aprovar=False,
            )
            RolePermission.objects.create(role=role_sec, permission=perm)
            RolePermission.objects.create(role=role_prof, permission=perm)

        UserRole.objects.create(user=self.secretario, role=role_sec, organization=self.org, ativo=True)
        UserRole.objects.create(user=self.professor, role=role_prof, organization=self.org, ativo=True)
        ClassTeacher.objects.create(class_group=self.turma, user=self.professor)

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'sec.escala@test.com', 'password': '123456'},
            format='json',
        )
        self.token = login.data['access']

    def _headers(self):
        return {
            'HTTP_AUTHORIZATION': f'Bearer {self.token}',
            'HTTP_X_ORGANIZATION_ID': str(self.org.id),
        }

    def test_bulk_create_schedule(self):
        response = self.client.post(
            '/api/v1/lesson-schedules/bulk/',
            {
                'lesson': self.lesson.id,
                'assignments': [
                    {'class_group': self.turma.id, 'professor': self.professor.id},
                ],
            },
            format='json',
            **self._headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            LessonSchedule.objects.filter(
                lesson=self.lesson,
                class_group=self.turma,
                professor=self.professor,
            ).exists()
        )

    def test_bulk_rejects_same_professor_in_two_classes_on_same_lesson(self):
        turma_jovens = ClassGroup.objects.create(
            organization=self.org,
            nome='Jovens',
            faixa_etaria='Jovens',
            cor='#111',
            ativa=True,
        )
        ClassTeacher.objects.create(
            class_group=turma_jovens,
            user=self.professor,
        )

        response = self.client.post(
            '/api/v1/lesson-schedules/bulk/',
            {
                'lesson': self.lesson.id,
                'assignments': [
                    {'class_group': self.turma.id, 'professor': self.professor.id},
                    {'class_group': turma_jovens.id, 'professor': self.professor.id},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('assignments', response.data)
        self.assertFalse(
            LessonSchedule.objects.filter(lesson=self.lesson).exists()
        )

    def test_rejects_professor_already_scheduled_on_same_date(self):
        turma_jovens = ClassGroup.objects.create(
            organization=self.org,
            nome='Jovens',
            faixa_etaria='Jovens',
            cor='#111',
            ativa=True,
        )
        outra_licao = Lesson.objects.create(
            organization=self.org,
            numero=2,
            tema='Outra lição no mesmo dia',
            data=self.lesson.data,
            revista='Jovens',
            trimestre=1,
            ano=2026,
        )
        LessonSchedule.objects.create(
            organization=self.org,
            lesson=self.lesson,
            class_group=self.turma,
            professor=self.professor,
        )

        response = self.client.post(
            '/api/v1/lesson-schedules/',
            {
                'lesson': outra_licao.id,
                'class_group': turma_jovens.id,
                'professor': self.professor.id,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('professor', response.data)

    def test_professor_lists_own_schedules(self):
        LessonSchedule.objects.create(
            organization=self.org,
            lesson=self.lesson,
            class_group=self.turma,
            professor=self.professor,
        )
        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'prof.escala@test.com', 'password': '123456'},
            format='json',
        )
        response = self.client.get(
            f'/api/v1/lesson-schedules/?lesson_id={self.lesson.id}',
            HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}',
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        self.assertEqual(response.status_code, 200)
        results = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(results), 1)
