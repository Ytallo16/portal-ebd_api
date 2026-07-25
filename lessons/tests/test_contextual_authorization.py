from datetime import date, timedelta

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
from attendance.models import AttendanceSheet
from classrooms.models import ClassGroup, ClassTeacher
from finance.models import Offering
from lessons.models import Lesson, LessonSchedule, Trimester
from lessons.services import (
    can_edit_class_lesson_registration,
    can_edit_lesson,
    can_manage_lessons,
)
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership


class ContextualLessonAuthorizationTests(APITestCase):
    def setUp(self):
        self.campo_a = self._create_campo('Campo A', 'CA')
        self.org_a = self._create_church('Igreja A', 'IA', self.campo_a)
        self.campo_b = self._create_campo('Campo B', 'CB')
        self.org_b = self._create_church('Igreja B', 'IB', self.campo_b)

        self.class_a = self._create_class(self.org_a, 'Adultos A')
        self.class_b = self._create_class(self.org_b, 'Adultos B')
        self.class_b_other = self._create_class(self.org_b, 'Jovens B')
        self.lesson_a = self._create_lesson(self.org_a, 1, 'Lição A')
        self.lesson_b = self._create_lesson(self.org_b, 1, 'Lição B')
        self.lesson_b_other = self._create_lesson(self.org_b, 2, 'Lição B 2')

        self.admin_role = Role.objects.create(nome=ROLE_ADMINISTRADOR)
        self.field_secretary_role = Role.objects.create(nome=ROLE_SECRETARIO_CAMPO)
        self.church_secretary_role = Role.objects.create(nome=ROLE_SECRETARIO_IGREJA)
        self.professor_role = Role.objects.create(nome=ROLE_PROFESSOR)

        for module in ('licoes', 'financeiro', 'turmas', 'usuarios'):
            permission = ModulePermission.objects.create(
                modulo=module,
                visualizar=True,
                criar=True,
                editar=True,
                excluir=True,
                aprovar=True,
            )
            for role in (
                self.field_secretary_role,
                self.church_secretary_role,
                self.professor_role,
            ):
                RolePermission.objects.create(role=role, permission=permission)

        self.mixed_user = self._create_user('misto@teste.com', 'Usuário Misto')
        self._add_membership(self.mixed_user, self.org_a)
        self._add_membership(self.mixed_user, self.org_b)
        UserRole.objects.create(
            user=self.mixed_user,
            role=self.church_secretary_role,
            organization=self.org_a,
            ativo=True,
        )
        UserRole.objects.create(
            user=self.mixed_user,
            role=self.professor_role,
            organization=self.org_b,
            ativo=True,
        )
        ClassTeacher.objects.create(class_group=self.class_b, user=self.mixed_user)

        self.same_org_manager = self._create_user(
            'gestor.misto@teste.com',
            'Gestor Misto',
        )
        self._add_membership(self.same_org_manager, self.org_b)
        for role in (self.church_secretary_role, self.professor_role):
            UserRole.objects.create(
                user=self.same_org_manager,
                role=role,
                organization=self.org_b,
                ativo=True,
            )
        ClassTeacher.objects.create(
            class_group=self.class_b,
            user=self.same_org_manager,
        )

        self.field_secretary = self._create_user(
            'campo.b@teste.com',
            'Secretário Campo B',
        )
        self._add_membership(self.field_secretary, self.campo_b)
        UserRole.objects.create(
            user=self.field_secretary,
            role=self.field_secretary_role,
            organization=self.campo_b,
            ativo=True,
        )

        self.admin = self._create_user('admin.contexto@teste.com', 'Admin')
        UserRole.objects.create(
            user=self.admin,
            role=self.admin_role,
            organization=None,
            ativo=True,
        )

        self.role_target = self._create_user(
            'alvo.papel@teste.com',
            'Alvo Papel',
        )
        self._add_membership(self.role_target, self.org_b)

        # Torna a lição visível para o professor no queryset restrito, sem concluí-la.
        AttendanceSheet.objects.create(
            lesson=self.lesson_b,
            class_group=self.class_b,
            professor=self.mixed_user,
        )

    def _create_campo(self, nome, sigla):
        return Organization.objects.create(
            nome=nome,
            sigla=sigla,
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )

    def _create_church(self, nome, sigla, parent):
        return Organization.objects.create(
            nome=nome,
            sigla=sigla,
            tipo=TIPO_IGREJA,
            parent=parent,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )

    def _create_class(self, organization, nome):
        return ClassGroup.objects.create(
            organization=organization,
            nome=nome,
            faixa_etaria='Adultos',
            cor='#123456',
            ativa=True,
        )

    def _create_lesson(self, organization, numero, tema):
        return Lesson.objects.create(
            organization=organization,
            numero=numero,
            tema=tema,
            data=date.today() - timedelta(days=7),
            revista='Adultos',
            trimestre=1,
            ano=2026,
        )

    def _create_user(self, email, nome):
        return User.objects.create_user(email=email, password='123456', nome=nome)

    def _add_membership(self, user, organization):
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            ativo=True,
        )

    def _authenticate(self, user, organization):
        self.client.force_authenticate(user=user)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(organization.id))

    def test_roles_from_another_church_do_not_authorize_lesson_management(self):
        self.assertTrue(can_manage_lessons(self.mixed_user, self.org_a))
        self.assertFalse(can_manage_lessons(self.mixed_user, self.org_b))
        self.assertFalse(can_edit_lesson(self.mixed_user, self.lesson_b))
        self.assertFalse(
            can_edit_class_lesson_registration(
                self.mixed_user,
                self.class_b_other,
                self.lesson_b,
            )
        )
        self.assertTrue(can_manage_lessons(self.admin, self.org_b))

    def test_cross_context_professor_cannot_mutate_secretary_only_resources(self):
        self._authenticate(self.mixed_user, self.org_b)

        schedule = self.client.post(
            '/api/v1/lesson-schedules/',
            {
                'lesson': self.lesson_b.id,
                'class_group': self.class_b.id,
                'professor': None,
            },
            format='json',
        )
        bulk_schedule = self.client.post(
            '/api/v1/lesson-schedules/bulk/',
            {
                'lesson': self.lesson_b.id,
                'assignments': [
                    {'class_group': self.class_b.id, 'professor': None},
                ],
            },
            format='json',
        )
        trimester = self.client.post(
            '/api/v1/trimesters/',
            {'numero': 2, 'ano': 2026, 'titulo': '2º Trimestre'},
            format='json',
        )
        lesson_update = self.client.patch(
            f'/api/v1/lessons/{self.lesson_b.id}/',
            {'tema': 'Alteração indevida'},
            format='json',
        )
        lesson_finalize = self.client.post(
            f'/api/v1/lessons/{self.lesson_b.id}/finalize/',
        )

        for response in (
            schedule,
            bulk_schedule,
            trimester,
            lesson_update,
            lesson_finalize,
        ):
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.lesson_b.refresh_from_db()
        self.assertEqual(self.lesson_b.tema, 'Lição B')
        self.assertEqual(self.lesson_b.status, 'ABERTA')
        self.assertFalse(
            LessonSchedule.objects.filter(organization=self.org_b).exists()
        )
        self.assertFalse(
            Trimester.objects.filter(organization=self.org_b, numero=2).exists()
        )

    def test_role_hierarchy_from_another_org_does_not_allow_user_management(self):
        self._authenticate(self.mixed_user, self.org_b)

        create_user = self.client.post(
            '/api/v1/users/',
            {
                'nome': 'Novo Professor',
                'email': 'novo.professor@teste.com',
                'senha': '123456',
                'papel': ROLE_PROFESSOR,
            },
            format='json',
        )
        assign_role = self.client.post(
            '/api/v1/user-roles/',
            {
                'user': self.role_target.id,
                'role': self.professor_role.id,
                'organization': self.org_b.id,
                'ativo': True,
            },
            format='json',
        )

        self.assertEqual(create_user.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(assign_role.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email='novo.professor@teste.com').exists())
        self.assertFalse(
            UserRole.objects.filter(
                user=self.role_target,
                role=self.professor_role,
                organization=self.org_b,
                ativo=True,
            ).exists()
        )

    def test_church_and_field_secretaries_keep_legitimate_management(self):
        self._authenticate(self.mixed_user, self.org_a)
        local_response = self.client.post(
            '/api/v1/lesson-schedules/',
            {
                'lesson': self.lesson_a.id,
                'class_group': self.class_a.id,
                'professor': None,
            },
            format='json',
        )
        self.assertEqual(local_response.status_code, status.HTTP_201_CREATED)

        self._authenticate(self.field_secretary, self.org_b)
        field_response = self.client.post(
            '/api/v1/lesson-schedules/',
            {
                'lesson': self.lesson_b.id,
                'class_group': self.class_b.id,
                'professor': None,
            },
            format='json',
        )
        self.assertEqual(field_response.status_code, status.HTTP_201_CREATED)

    def test_schedule_create_and_update_reject_cross_organization_relations(self):
        self._authenticate(self.field_secretary, self.org_b)
        cross_create = self.client.post(
            '/api/v1/lesson-schedules/',
            {
                'lesson': self.lesson_a.id,
                'class_group': self.class_a.id,
                'professor': None,
            },
            format='json',
        )
        self.assertEqual(cross_create.status_code, status.HTTP_400_BAD_REQUEST)

        schedule = LessonSchedule.objects.create(
            organization=self.org_b,
            lesson=self.lesson_b,
            class_group=self.class_b,
        )
        cross_update = self.client.patch(
            f'/api/v1/lesson-schedules/{schedule.id}/',
            {
                'lesson': self.lesson_a.id,
                'class_group': self.class_a.id,
            },
            format='json',
        )

        self.assertEqual(cross_update.status_code, status.HTTP_400_BAD_REQUEST)
        schedule.refresh_from_db()
        self.assertEqual(schedule.organization_id, self.org_b.id)
        self.assertEqual(schedule.lesson_id, self.lesson_b.id)
        self.assertEqual(schedule.class_group_id, self.class_b.id)

    def test_secretary_professor_in_same_org_is_not_filtered_as_teacher_only(self):
        LessonSchedule.objects.create(
            organization=self.org_b,
            lesson=self.lesson_b,
            class_group=self.class_b,
            professor=self.same_org_manager,
        )
        LessonSchedule.objects.create(
            organization=self.org_b,
            lesson=self.lesson_b,
            class_group=self.class_b_other,
            professor=None,
        )
        self._authenticate(self.same_org_manager, self.org_b)

        schedules = self.client.get('/api/v1/lesson-schedules/')
        classes = self.client.get('/api/v1/classes/')

        self.assertEqual(schedules.status_code, status.HTTP_200_OK)
        schedule_results = schedules.data.get('results', schedules.data)
        self.assertEqual(len(schedule_results), 2)
        self.assertEqual(classes.status_code, status.HTTP_200_OK)
        class_results = classes.data.get('results', classes.data)
        self.assertEqual(
            {item['id'] for item in class_results},
            {self.class_b.id, self.class_b_other.id},
        )

    def test_offering_rejects_cross_org_inactive_and_relation_changes(self):
        self._authenticate(self.mixed_user, self.org_b)

        cross_org = self.client.post(
            '/api/v1/offerings/',
            {
                'lesson': self.lesson_a.id,
                'class_group': self.class_a.id,
                'data': date.today(),
                'valor': '10.00',
            },
            format='json',
        )
        mixed_org = self.client.post(
            '/api/v1/offerings/',
            {
                'lesson': self.lesson_b.id,
                'class_group': self.class_a.id,
                'data': date.today(),
                'valor': '10.00',
            },
            format='json',
        )

        inactive_lesson = self._create_lesson(self.org_b, 3, 'Lição inativa')
        inactive_lesson.is_active = False
        inactive_lesson.save(update_fields=['is_active'])
        inactive = self.client.post(
            '/api/v1/offerings/',
            {
                'lesson': inactive_lesson.id,
                'class_group': self.class_b.id,
                'data': date.today(),
                'valor': '10.00',
            },
            format='json',
        )
        inactive_class = self._create_class(self.org_b, 'Turma inativa')
        inactive_class.ativa = False
        inactive_class.save(update_fields=['ativa'])
        inactive_class_response = self.client.post(
            '/api/v1/offerings/',
            {
                'lesson': self.lesson_b.id,
                'class_group': inactive_class.id,
                'data': date.today(),
                'valor': '10.00',
            },
            format='json',
        )

        self.assertEqual(cross_org.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(mixed_org.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(inactive.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            inactive_class_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertFalse(Offering.objects.exists())

        valid = self.client.post(
            '/api/v1/offerings/',
            {
                'lesson': self.lesson_b.id,
                'class_group': self.class_b.id,
                'data': date.today(),
                'valor': '15.00',
            },
            format='json',
        )
        self.assertEqual(valid.status_code, status.HTTP_201_CREATED)

        relation_change = self.client.patch(
            f"/api/v1/offerings/{valid.data['id']}/",
            {
                'lesson': self.lesson_b_other.id,
                'class_group': self.class_b_other.id,
            },
            format='json',
        )
        self.assertEqual(relation_change.status_code, status.HTTP_400_BAD_REQUEST)
        offering = Offering.objects.get(pk=valid.data['id'])
        self.assertEqual(offering.lesson_id, self.lesson_b.id)
        self.assertEqual(offering.class_group_id, self.class_b.id)
