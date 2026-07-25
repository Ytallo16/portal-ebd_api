from datetime import date, timedelta

from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from attendance.models import AttendanceRecord, AttendanceSheet
from classrooms.models import ClassGroup, ClassTeacher
from finance.models import Offering
from lessons.models import Lesson, LessonSchedule
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership
from students.models import Student


class AttendanceFlowTests(APITestCase):
    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo Presença',
            sigla='CP',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.org = Organization.objects.create(
            nome='Org Presença',
            sigla='OP',
            tipo=TIPO_IGREJA,
            parent=self.campo,
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

    def save_registration(
        self,
        *,
        lesson=None,
        class_group=None,
        records=None,
        registration_status='CONCLUIDA',
        **overrides,
    ):
        lesson = lesson or self.lesson
        class_group = class_group or self.class_group
        payload = {
            'status': registration_status,
            'professor': None,
            'professor_presente': False,
            'visitantes': 1,
            'biblias': 10,
            'revistas': 8,
            'oferta_valor': '25.00',
            'records': (
                records
                if records is not None
                else [{'student': self.student.id, 'presente': True}]
            ),
            **overrides,
        }
        return self.client.put(
            f'/api/v1/lessons/{lesson.id}/classes/{class_group.id}/attendance',
            payload,
            format='json',
        )

    def test_full_attendance_and_finalize_lesson_flow(self):
        registration = self.save_registration()
        self.assertEqual(registration.status_code, status.HTTP_200_OK)
        self.assertEqual(registration.data['status'], 'CONCLUIDA')
        self.assertEqual(len(registration.data['records']), 1)
        self.assertTrue(registration.data['records'][0]['presente'])

        finalize_lesson = self.client.post(f'/api/v1/lessons/{self.lesson.id}/finalize/')
        self.assertEqual(finalize_lesson.status_code, status.HTTP_200_OK)
        self.assertEqual(finalize_lesson.data['status'], 'FINALIZADA')

    def test_finalize_lesson_without_sheet_fails(self):
        response = self.client.post(f'/api/v1/lessons/{self.lesson.id}/finalize/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('turmas_pendentes', response.data)

    def test_finalize_lesson_requires_all_active_classes(self):
        ClassGroup.objects.create(
            organization=self.org,
            nome='Jovens',
            faixa_etaria='18-25',
            cor='#0C7A43',
            created_by=self.user,
        )

        registration = self.save_registration()
        self.assertEqual(registration.status_code, status.HTTP_200_OK)

        response = self.client.post(f'/api/v1/lessons/{self.lesson.id}/finalize/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Jovens', response.data['turmas_pendentes'])

    def test_opening_attendance_does_not_create_sheet(self):
        response = self.client.get(
            f'/api/v1/lessons/{self.lesson.id}/classes/{self.class_group.id}/attendance'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(AttendanceSheet.objects.count(), 0)

    def test_registration_has_explicit_draft_and_completed_states(self):
        draft = self.save_registration(registration_status='RASCUNHO')
        self.assertEqual(draft.status_code, status.HTTP_200_OK)
        self.assertEqual(draft.data['status'], 'RASCUNHO')
        self.assertIsNone(draft.data['finalized_at'])

        finalize_lesson = self.client.post(f'/api/v1/lessons/{self.lesson.id}/finalize/')
        self.assertEqual(finalize_lesson.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(self.class_group.nome, finalize_lesson.data['turmas_pendentes'])

        completed = self.save_registration(registration_status='CONCLUIDA')
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        self.assertEqual(completed.data['status'], 'CONCLUIDA')
        self.assertIsNotNone(completed.data['finalized_at'])

    def test_draft_deactivates_offering_and_completion_reuses_it(self):
        existing = Offering.objects.create(
            organization=self.org,
            lesson=self.lesson,
            class_group=self.class_group,
            data=self.lesson.data,
            valor='99.00',
        )

        draft = self.save_registration(
            registration_status='RASCUNHO',
            oferta_valor='25.00',
        )

        self.assertEqual(draft.status_code, status.HTTP_200_OK)
        existing.refresh_from_db()
        self.assertFalse(existing.is_active)
        self.assertIsNotNone(existing.deleted_at)
        self.assertFalse(
            Offering.objects.filter(
                lesson=self.lesson,
                class_group=self.class_group,
                is_active=True,
            ).exists()
        )

        completed = self.save_registration(
            registration_status='CONCLUIDA',
            oferta_valor='42.50',
        )

        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        existing.refresh_from_db()
        self.assertTrue(existing.is_active)
        self.assertIsNone(existing.deleted_at)
        self.assertEqual(str(existing.valor), '42.50')
        self.assertEqual(
            Offering.objects.filter(
                lesson=self.lesson,
                class_group=self.class_group,
            ).count(),
            1,
        )

    def test_professor_presence_update_does_not_reopen_completed_registration(self):
        completed = self.save_registration()

        response = self.client.patch(
            f"/api/v1/attendance-sheets/{completed.data['id']}/",
            {'professor_presente': True},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'CONCLUIDA')
        self.assertIsNotNone(response.data['finalized_at'])

    def test_finalized_lesson_cannot_return_attendance_to_draft(self):
        completed = self.save_registration()
        original_finalized_at = AttendanceSheet.objects.get(
            pk=completed.data['id']
        ).finalized_at
        finalize_lesson = self.client.post(
            f'/api/v1/lessons/{self.lesson.id}/finalize/'
        )
        self.assertEqual(finalize_lesson.status_code, status.HTTP_200_OK)

        response = self.save_registration(
            registration_status='RASCUNHO',
            biblias=99,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
        sheet = AttendanceSheet.objects.get(
            lesson=self.lesson,
            class_group=self.class_group,
        )
        self.assertEqual(sheet.biblias, 10)
        self.assertEqual(sheet.finalized_at, original_finalized_at)

    def test_correction_after_lesson_finalization_stays_completed(self):
        completed = self.save_registration()
        finalize_lesson = self.client.post(
            f'/api/v1/lessons/{self.lesson.id}/finalize/'
        )
        self.assertEqual(finalize_lesson.status_code, status.HTTP_200_OK)

        totals = self.client.patch(
            f"/api/v1/attendance-sheets/{completed.data['id']}/",
            {'biblias': 12},
            format='json',
        )
        records = self.client.post(
            f"/api/v1/attendance-sheets/{completed.data['id']}/records/",
            {'records': [{'student': self.student.id, 'presente': False}]},
            format='json',
        )

        self.assertEqual(totals.status_code, status.HTTP_200_OK)
        self.assertEqual(totals.data['status'], 'CONCLUIDA')
        self.assertEqual(records.status_code, status.HTTP_200_OK)
        self.assertEqual(records.data['status'], 'CONCLUIDA')
        sheet = AttendanceSheet.objects.get(pk=completed.data['id'])
        self.assertIsNotNone(sheet.finalized_at)
        self.assertEqual(sheet.biblias, 12)
        self.assertFalse(sheet.records.get(student=self.student).presente)

    def test_student_record_update_reopens_completed_registration(self):
        completed = self.save_registration()

        response = self.client.post(
            f"/api/v1/attendance-sheets/{completed.data['id']}/records/",
            {'records': [{'student': self.student.id, 'presente': False}]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'RASCUNHO')
        self.assertIsNone(response.data['finalized_at'])
        self.assertFalse(
            Offering.objects.filter(
                organization=self.org,
                lesson=self.lesson,
                class_group=self.class_group,
                is_active=True,
            ).exists()
        )

    def test_completed_registration_requires_every_active_student_atomically(self):
        Student.objects.create(
            organization=self.org,
            class_group=self.class_group,
            nome='Aluno 2',
            sexo='F',
            data_nascimento=date(2001, 1, 1),
            created_by=self.user,
        )

        response = self.save_registration(
            records=[{'student': self.student.id, 'presente': True}],
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('records', response.data)
        self.assertFalse(AttendanceSheet.objects.exists())

    def test_student_from_another_class_is_rejected_without_partial_update(self):
        another_class = ClassGroup.objects.create(
            organization=self.org,
            nome='Jovens',
            faixa_etaria='18-25',
            cor='#0C7A43',
            created_by=self.user,
        )
        another_student = Student.objects.create(
            organization=self.org,
            class_group=another_class,
            nome='Aluno de outra turma',
            sexo='M',
            data_nascimento=date(2002, 1, 1),
            created_by=self.user,
        )
        draft = self.save_registration(
            registration_status='RASCUNHO',
            biblias=3,
        )
        self.assertEqual(draft.status_code, status.HTTP_200_OK)

        invalid = self.save_registration(
            registration_status='RASCUNHO',
            biblias=99,
            records=[
                {'student': self.student.id, 'presente': False},
                {'student': another_student.id, 'presente': True},
            ],
        )

        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        sheet = AttendanceSheet.objects.get(
            lesson=self.lesson,
            class_group=self.class_group,
        )
        self.assertEqual(sheet.biblias, 3)
        self.assertTrue(sheet.records.get(student=self.student).presente)

    def test_put_replaces_active_records_but_preserves_inactive_history(self):
        active_student = Student.objects.create(
            organization=self.org,
            class_group=self.class_group,
            nome='Aluno ativo removido do payload',
            sexo='F',
            data_nascimento=date(2001, 1, 1),
            created_by=self.user,
        )
        historical_student = Student.objects.create(
            organization=self.org,
            class_group=self.class_group,
            nome='Aluno histórico',
            sexo='M',
            data_nascimento=date(1999, 1, 1),
            ativo=False,
            is_active=False,
            created_by=self.user,
        )
        initial = self.save_registration(
            registration_status='RASCUNHO',
            records=[
                {'student': self.student.id, 'presente': True},
                {'student': active_student.id, 'presente': False},
            ],
        )
        sheet = AttendanceSheet.objects.get(pk=initial.data['id'])
        AttendanceRecord.objects.create(
            attendance_sheet=sheet,
            student=historical_student,
            presente=True,
            created_by=self.user,
        )

        replacement = self.save_registration(
            registration_status='RASCUNHO',
            records=[{'student': self.student.id, 'presente': False}],
        )

        self.assertEqual(replacement.status_code, status.HTTP_200_OK)
        records_by_student = {
            record['student']: record for record in replacement.data['records']
        }
        self.assertEqual(
            set(records_by_student),
            {self.student.id, historical_student.id},
        )
        self.assertNotIn(active_student.id, records_by_student)
        self.assertEqual(
            records_by_student[historical_student.id]['aluno_nome'],
            'Aluno histórico',
        )
        self.assertTrue(records_by_student[historical_student.id]['presente'])

    def test_historical_sheet_of_inactive_class_is_read_only(self):
        completed = self.save_registration()
        self.class_group.ativa = False
        self.class_group.is_active = False
        self.class_group.save(update_fields=['ativa', 'is_active', 'updated_at'])
        self.lesson.is_active = False
        self.lesson.save(update_fields=['is_active', 'updated_at'])

        get_response = self.client.get(
            f'/api/v1/lessons/{self.lesson.id}/classes/{self.class_group.id}/attendance'
        )
        put_response = self.save_registration(
            registration_status='CONCLUIDA',
            biblias=99,
        )

        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertEqual(get_response.data['id'], completed.data['id'])
        self.assertEqual(put_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            AttendanceSheet.objects.get(pk=completed.data['id']).biblias,
            10,
        )

    def test_direct_put_requires_create_permission_only_when_sheet_is_absent(self):
        frequency_permission = ModulePermission.objects.get(modulo='frequencia')
        frequency_permission.criar = True
        frequency_permission.editar = False
        frequency_permission.save(update_fields=['criar', 'editar', 'updated_at'])
        role = Role.objects.create(nome='SECRETARIO_IGREJA')
        RolePermission.objects.create(role=role, permission=frequency_permission)
        creator = User.objects.create_user(
            email='creator-attendance@test.com',
            password='123456',
            nome='Criador de chamada',
        )
        OrganizationMembership.objects.create(
            user=creator,
            organization=self.org,
            ativo=True,
        )
        UserRole.objects.create(
            user=creator,
            role=role,
            organization=self.org,
            ativo=True,
        )
        login = self.client.post(
            '/api/v1/auth/login',
            {'email': creator.email, 'password': '123456'},
            format='json',
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}",
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

        created = self.save_registration(registration_status='RASCUNHO')
        denied_edit = self.save_registration(
            registration_status='RASCUNHO',
            biblias=99,
        )

        self.assertEqual(created.status_code, status.HTTP_200_OK)
        self.assertEqual(denied_edit.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            AttendanceSheet.objects.get(pk=created.data['id']).biblias,
            10,
        )

    def test_direct_put_requires_edit_permission_when_sheet_exists(self):
        existing = self.save_registration(registration_status='RASCUNHO')
        frequency_permission = ModulePermission.objects.get(modulo='frequencia')
        frequency_permission.criar = False
        frequency_permission.editar = True
        frequency_permission.save(update_fields=['criar', 'editar', 'updated_at'])
        role = Role.objects.create(nome='SECRETARIO_IGREJA')
        RolePermission.objects.create(role=role, permission=frequency_permission)
        editor = User.objects.create_user(
            email='editor-attendance@test.com',
            password='123456',
            nome='Editor de chamada',
        )
        OrganizationMembership.objects.create(
            user=editor,
            organization=self.org,
            ativo=True,
        )
        UserRole.objects.create(
            user=editor,
            role=role,
            organization=self.org,
            ativo=True,
        )
        login = self.client.post(
            '/api/v1/auth/login',
            {'email': editor.email, 'password': '123456'},
            format='json',
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}",
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

        edited = self.save_registration(
            registration_status='RASCUNHO',
            biblias=17,
        )

        self.assertEqual(edited.status_code, status.HTTP_200_OK)
        self.assertEqual(edited.data['id'], existing.data['id'])
        self.assertEqual(edited.data['biblias'], 17)

    def test_professor_field_rejects_membership_without_professor_role(self):
        member = User.objects.create_user(
            email='member-not-professor@test.com',
            password='123456',
            nome='Membro',
        )
        OrganizationMembership.objects.create(
            user=member,
            organization=self.org,
            ativo=True,
        )
        ClassTeacher.objects.create(class_group=self.class_group, user=member)

        response = self.save_registration(professor=member.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('perfil PROFESSOR ativo', str(response.data['professor']))
        self.assertFalse(AttendanceSheet.objects.exists())

    def test_professor_field_rejects_professor_not_linked_to_class(self):
        professor = User.objects.create_user(
            email='professor-other-class@test.com',
            password='123456',
            nome='Professor sem turma',
        )
        OrganizationMembership.objects.create(
            user=professor,
            organization=self.org,
            ativo=True,
        )
        role = Role.objects.create(nome='PROFESSOR')
        UserRole.objects.create(
            user=professor,
            role=role,
            organization=self.org,
            ativo=True,
        )

        response = self.save_registration(professor=professor.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('não está vinculado', str(response.data['professor']))
        self.assertFalse(AttendanceSheet.objects.exists())

    def test_professor_field_accepts_professor_scheduled_for_lesson(self):
        professor = User.objects.create_user(
            email='scheduled-professor@test.com',
            password='123456',
            nome='Professor escalado',
        )
        OrganizationMembership.objects.create(
            user=professor,
            organization=self.org,
            ativo=True,
        )
        role = Role.objects.create(nome='PROFESSOR')
        RolePermission.objects.create(
            role=role,
            permission=ModulePermission.objects.get(modulo='frequencia'),
        )
        UserRole.objects.create(
            user=professor,
            role=role,
            organization=self.org,
            ativo=True,
        )
        LessonSchedule.objects.create(
            organization=self.org,
            lesson=self.lesson,
            class_group=self.class_group,
            professor=professor,
        )
        login = self.client.post(
            '/api/v1/auth/login',
            {'email': professor.email, 'password': '123456'},
            format='json',
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}",
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

        response = self.save_registration(professor=professor.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['professor'], professor.id)

    def test_lesson_and_class_from_another_organization_are_rejected(self):
        another_org = Organization.objects.create(
            nome='Outra igreja',
            sigla='OI',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        another_class = ClassGroup.objects.create(
            organization=another_org,
            nome='Outra turma',
            faixa_etaria='18-25',
            cor='#0C7A43',
            created_by=self.user,
        )
        another_lesson = Lesson.objects.create(
            organization=another_org,
            numero=2,
            tema='Outra lição',
            data=date.today(),
            revista='Revista',
            trimestre=1,
            ano=2026,
            created_by=self.user,
        )

        wrong_class = self.client.put(
            f'/api/v1/lessons/{self.lesson.id}/classes/{another_class.id}/attendance',
            {'status': 'RASCUNHO', 'records': []},
            format='json',
        )
        wrong_lesson = self.client.put(
            f'/api/v1/lessons/{another_lesson.id}/classes/{self.class_group.id}/attendance',
            {'status': 'RASCUNHO', 'records': []},
            format='json',
        )

        self.assertEqual(wrong_class.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(wrong_lesson.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(AttendanceSheet.objects.exists())

    def test_legacy_sheet_endpoint_rejects_cross_organization_context(self):
        another_org = Organization.objects.create(
            nome='Igreja externa',
            sigla='IE',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        another_class = ClassGroup.objects.create(
            organization=another_org,
            nome='Turma externa',
            faixa_etaria='18-25',
            cor='#0C7A43',
            created_by=self.user,
        )

        response = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': self.lesson.id,
                'class_group': another_class.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(AttendanceSheet.objects.exists())

    def test_legacy_records_endpoint_rejects_student_from_another_class(self):
        another_class = ClassGroup.objects.create(
            organization=self.org,
            nome='Adolescentes',
            faixa_etaria='12-17',
            cor='#0C7A43',
            created_by=self.user,
        )
        another_student = Student.objects.create(
            organization=self.org,
            class_group=another_class,
            nome='Aluno externo',
            sexo='M',
            data_nascimento=date(2008, 1, 1),
            created_by=self.user,
        )
        sheet_response = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': self.lesson.id,
                'class_group': self.class_group.id,
            },
            format='json',
        )

        response = self.client.post(
            f"/api/v1/attendance-sheets/{sheet_response.data['id']}/records/",
            {
                'records': [
                    {'student': self.student.id, 'presente': True},
                    {'student': another_student.id, 'presente': True},
                ]
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            AttendanceSheet.objects.get(pk=sheet_response.data['id']).records.exists()
        )

    def test_professor_direct_endpoint_is_limited_to_own_classes(self):
        professor = User.objects.create_user(
            email='scoped-professor@test.com',
            password='123456',
            nome='Professor limitado',
        )
        OrganizationMembership.objects.create(
            user=professor,
            organization=self.org,
            ativo=True,
        )
        role, _ = Role.objects.get_or_create(
            nome='PROFESSOR',
            defaults={'descricao': 'Professor', 'ativo': True},
        )
        for module in ['licoes', 'frequencia', 'turmas', 'alunos']:
            perm, _ = ModulePermission.objects.get_or_create(
                modulo=module,
                defaults={
                    'visualizar': True,
                    'criar': True,
                    'editar': True,
                    'excluir': False,
                    'aprovar': False,
                },
            )
            RolePermission.objects.get_or_create(role=role, permission=perm)
        UserRole.objects.create(
            user=professor,
            role=role,
            organization=self.org,
            ativo=True,
        )
        ClassTeacher.objects.create(class_group=self.class_group, user=professor)
        another_class = ClassGroup.objects.create(
            organization=self.org,
            nome='Turma alheia',
            faixa_etaria='18-25',
            cor='#0C7A43',
            created_by=self.user,
        )

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': professor.email, 'password': '123456'},
            format='json',
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}",
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

        own = self.client.put(
            f'/api/v1/lessons/{self.lesson.id}/classes/{self.class_group.id}/attendance',
            {
                'status': 'CONCLUIDA',
                'professor': professor.id,
                'records': [{'student': self.student.id, 'presente': True}],
            },
            format='json',
        )
        other = self.client.put(
            f'/api/v1/lessons/{self.lesson.id}/classes/{another_class.id}/attendance',
            {'status': 'RASCUNHO', 'records': []},
            format='json',
        )

        self.assertEqual(own.status_code, status.HTTP_200_OK)
        self.assertEqual(other.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            AttendanceSheet.objects.filter(class_group=another_class).exists()
        )

    def test_professor_cannot_finalize_lesson(self):
        professor = User.objects.create_user(
            email='prof@test.com',
            password='123456',
            nome='Professor',
        )
        OrganizationMembership.objects.create(
            user=professor,
            organization=self.org,
            ativo=True,
        )
        role, _ = Role.objects.get_or_create(
            nome='PROFESSOR',
            defaults={'descricao': 'Professor', 'ativo': True},
        )
        for module in ['licoes', 'frequencia', 'turmas', 'alunos']:
            perm, _ = ModulePermission.objects.get_or_create(
                modulo=module,
                defaults={
                    'visualizar': True,
                    'criar': True,
                    'editar': True,
                    'excluir': False,
                    'aprovar': False,
                },
            )
            RolePermission.objects.get_or_create(role=role, permission=perm)
        UserRole.objects.create(user=professor, role=role, organization=self.org, ativo=True)
        ClassTeacher.objects.create(class_group=self.class_group, user=professor)

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'prof@test.com', 'password': '123456'},
            format='json',
        )
        token = login.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token}',
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

        create_sheet = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': self.lesson.id,
                'class_group': self.class_group.id,
                'professor': professor.id,
                'visitantes': 0,
                'biblias': 0,
                'revistas': 0,
                'oferta_valor': '0.00',
            },
            format='json',
        )
        self.assertEqual(create_sheet.status_code, status.HTTP_201_CREATED)
        sheet_id = create_sheet.data['id']
        self.client.post(
            f'/api/v1/attendance-sheets/{sheet_id}/records/',
            {'records': [{'student': self.student.id, 'presente': True}]},
            format='json',
        )

        response = self.client.post(f'/api/v1/lessons/{self.lesson.id}/finalize/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_professor_can_update_ebd_totals_on_lesson_day(self):
        professor = User.objects.create_user(
            email='prof2@test.com',
            password='123456',
            nome='Professor 2',
        )
        OrganizationMembership.objects.create(
            user=professor,
            organization=self.org,
            ativo=True,
        )
        role, _ = Role.objects.get_or_create(
            nome='PROFESSOR',
            defaults={'descricao': 'Professor', 'ativo': True},
        )
        for module in ['licoes', 'frequencia', 'turmas', 'alunos', 'financeiro']:
            perm, _ = ModulePermission.objects.get_or_create(
                modulo=module,
                defaults={
                    'visualizar': True,
                    'criar': True,
                    'editar': True,
                    'excluir': False,
                    'aprovar': False,
                },
            )
            RolePermission.objects.get_or_create(role=role, permission=perm)
        UserRole.objects.create(user=professor, role=role, organization=self.org, ativo=True)
        ClassTeacher.objects.create(class_group=self.class_group, user=professor)

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'prof2@test.com', 'password': '123456'},
            format='json',
        )
        token = login.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token}',
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

        create_sheet = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': self.lesson.id,
                'class_group': self.class_group.id,
                'professor': professor.id,
                'visitantes': 1,
                'biblias': 2,
                'revistas': 3,
                'oferta_valor': '10.00',
            },
            format='json',
        )
        self.assertEqual(create_sheet.status_code, status.HTTP_201_CREATED)
        sheet_id = create_sheet.data['id']

        patch = self.client.patch(
            f'/api/v1/attendance-sheets/{sheet_id}/',
            {
                'visitantes': 4,
                'biblias': 5,
                'revistas': 6,
                'oferta_valor': '42.50',
            },
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['biblias'], 5)
        self.assertEqual(patch.data['revistas'], 6)
        self.assertEqual(str(patch.data['oferta_valor']), '42.50')
        self.assertFalse(
            Offering.objects.filter(
                lesson_id=self.lesson.id,
                class_group_id=self.class_group.id,
                organization=self.org,
                is_active=True,
            ).exists()
        )

        completed = self.client.put(
            f'/api/v1/lessons/{self.lesson.id}/classes/{self.class_group.id}/attendance',
            {
                'status': 'CONCLUIDA',
                'professor': professor.id,
                'professor_presente': True,
                'visitantes': 4,
                'biblias': 5,
                'revistas': 6,
                'oferta_valor': '42.50',
                'records': [
                    {'student': self.student.id, 'presente': True},
                ],
            },
            format='json',
        )
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        offering = Offering.objects.get(
            lesson_id=self.lesson.id,
            class_group_id=self.class_group.id,
            organization=self.org,
            is_active=True,
        )
        self.assertEqual(str(offering.valor), '42.50')

    def test_professor_can_register_on_past_lesson_date(self):
        past_lesson = Lesson.objects.create(
            organization=self.org,
            numero=99,
            tema='Lição passada',
            data=date.today() - timedelta(days=21),
            revista='Revista',
            trimestre=1,
            ano=2026,
            status='ABERTA',
            created_by=self.user,
        )
        professor = User.objects.create_user(
            email='prof3@test.com',
            password='123456',
            nome='Professor 3',
        )
        OrganizationMembership.objects.create(
            user=professor,
            organization=self.org,
            ativo=True,
        )
        role, _ = Role.objects.get_or_create(
            nome='PROFESSOR',
            defaults={'descricao': 'Professor', 'ativo': True},
        )
        for module in ['licoes', 'frequencia', 'turmas', 'alunos']:
            perm, _ = ModulePermission.objects.get_or_create(
                modulo=module,
                defaults={
                    'visualizar': True,
                    'criar': True,
                    'editar': True,
                    'excluir': False,
                    'aprovar': False,
                },
            )
            RolePermission.objects.get_or_create(role=role, permission=perm)
        UserRole.objects.create(user=professor, role=role, organization=self.org, ativo=True)
        ClassTeacher.objects.create(class_group=self.class_group, user=professor)

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'prof3@test.com', 'password': '123456'},
            format='json',
        )
        token = login.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token}',
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

        create_sheet = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': past_lesson.id,
                'class_group': self.class_group.id,
                'professor': professor.id,
                'visitantes': 2,
                'biblias': 3,
                'revistas': 4,
                'oferta_valor': '15.00',
            },
            format='json',
        )
        self.assertEqual(create_sheet.status_code, status.HTTP_201_CREATED)
