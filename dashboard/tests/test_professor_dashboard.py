from datetime import date, timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from attendance.models import AttendanceRecord, AttendanceSheet
from classrooms.models import ClassGroup, ClassTeacher
from dashboard.services import _build_aniversariantes, build_professor_dashboard
from lessons.models import Lesson, LessonSchedule, Trimester
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership
from students.models import Student


class ProfessorDashboardTests(APITestCase):
    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo Dash Prof',
            sigla='CDP',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.org = Organization.objects.create(
            nome='Igreja Dash Prof',
            sigla='IDP',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.turma_a = ClassGroup.objects.create(
            organization=self.org,
            nome='Adultos',
            faixa_etaria='Adultos',
            cor='#125A94',
            ativa=True,
        )
        self.turma_b = ClassGroup.objects.create(
            organization=self.org,
            nome='Jovens',
            faixa_etaria='Jovens',
            cor='#0C7A43',
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
        self.lesson_1 = Lesson.objects.create(
            organization=self.org,
            numero=1,
            tema='Lição 1',
            data=today - timedelta(days=14),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )
        self.lesson_2 = Lesson.objects.create(
            organization=self.org,
            numero=2,
            tema='Lição 2',
            data=today - timedelta(days=7),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )
        self.lesson_3 = Lesson.objects.create(
            organization=self.org,
            numero=3,
            tema='Lição 3',
            data=today + timedelta(days=7),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )

        self.prof_a = User.objects.create_user(
            email='prof.adultos@test.com',
            password='123456',
            nome='Prof Adultos',
        )
        self.prof_b = User.objects.create_user(
            email='prof.jovens@test.com',
            password='123456',
            nome='Prof Jovens',
        )
        self.secretario = User.objects.create_user(
            email='sec@test.com',
            password='123456',
            nome='Secretario',
        )

        for user in (self.prof_a, self.prof_b, self.secretario):
            OrganizationMembership.objects.create(user=user, organization=self.org, ativo=True)

        role_prof = Role.objects.create(nome='PROFESSOR')
        role_sec = Role.objects.create(nome='SECRETARIO_IGREJA')
        for module in ('dashboard', 'licoes', 'frequencia', 'turmas', 'alunos'):
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

        UserRole.objects.create(user=self.prof_a, role=role_prof, organization=self.org, ativo=True)
        UserRole.objects.create(user=self.prof_b, role=role_prof, organization=self.org, ativo=True)
        UserRole.objects.create(user=self.secretario, role=role_sec, organization=self.org, ativo=True)

        ClassTeacher.objects.create(class_group=self.turma_a, user=self.prof_a)
        ClassTeacher.objects.create(class_group=self.turma_b, user=self.prof_b)

        self.aluno_presente = Student.objects.create(
            organization=self.org,
            class_group=self.turma_a,
            nome='Aluno Presente',
            sexo='M',
            data_nascimento=date.today().replace(year=2005),
            ativo=True,
        )
        self.aluno_faltoso = Student.objects.create(
            organization=self.org,
            class_group=self.turma_a,
            nome='Aluno Faltoso',
            sexo='F',
            data_nascimento=date(2006, 6, 15),
            ativo=True,
        )
        Student.objects.create(
            organization=self.org,
            class_group=self.turma_b,
            nome='Aluno Jovens',
            sexo='M',
            data_nascimento=date(2007, 1, 1),
            ativo=True,
        )

        self.sheet_1 = AttendanceSheet.objects.create(
            lesson=self.lesson_1,
            class_group=self.turma_a,
            professor=self.prof_a,
            professor_presente=True,
            visitantes=1,
            biblias=5,
            revistas=4,
            oferta_valor='10.00',
            finalized_at=timezone.now(),
        )
        AttendanceRecord.objects.create(
            attendance_sheet=self.sheet_1,
            student=self.aluno_presente,
            presente=True,
        )
        AttendanceRecord.objects.create(
            attendance_sheet=self.sheet_1,
            student=self.aluno_faltoso,
            presente=False,
        )

        self.sheet_2 = AttendanceSheet.objects.create(
            lesson=self.lesson_2,
            class_group=self.turma_a,
            professor=self.prof_a,
            professor_presente=True,
            visitantes=2,
            biblias=6,
            revistas=5,
            oferta_valor='15.50',
            finalized_at=timezone.now(),
        )
        AttendanceRecord.objects.create(
            attendance_sheet=self.sheet_2,
            student=self.aluno_presente,
            presente=True,
        )
        AttendanceRecord.objects.create(
            attendance_sheet=self.sheet_2,
            student=self.aluno_faltoso,
            presente=False,
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

    def test_professor_dashboard_returns_class_metrics(self):
        self._login('prof.adultos@test.com')
        response = self.client.get('/api/v1/dashboard/professor')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['turma']['nome'], 'Adultos')
        self.assertEqual(response.data['turma']['total_alunos'], 2)
        self.assertEqual(response.data['resumo']['pendencias_registro'], 0)
        self.assertEqual(response.data['licoes_pendentes'], [])
        self.assertEqual(len(response.data['evolucao_frequencia']), 2)
        self.assertEqual(response.data['ultimo_registro']['licao_numero'], 2)
        self.assertEqual(response.data['licoes_hoje'], [])
        ranking = {item['nome']: item for item in response.data['ranking_alunos']}
        self.assertEqual(len(ranking), 2)
        self.assertEqual(ranking['Aluno Faltoso']['ausencias'], 2)
        self.assertEqual(ranking['Aluno Presente']['presencas'], 2)

    def test_draft_sheet_is_pending_and_does_not_change_statistics(self):
        draft_lesson = Lesson.objects.create(
            organization=self.org,
            numero=4,
            tema='Lição em rascunho',
            data=timezone.localdate(),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )
        draft_sheet = AttendanceSheet.objects.create(
            lesson=draft_lesson,
            class_group=self.turma_a,
            professor=self.prof_a,
            visitantes=50,
            oferta_valor='999.00',
        )
        AttendanceRecord.objects.create(
            attendance_sheet=draft_sheet,
            student=self.aluno_presente,
            presente=False,
        )
        AttendanceRecord.objects.create(
            attendance_sheet=draft_sheet,
            student=self.aluno_faltoso,
            presente=True,
        )
        LessonSchedule.objects.create(
            organization=self.org,
            lesson=draft_lesson,
            class_group=self.turma_a,
            professor=self.prof_a,
        )

        payload = build_professor_dashboard(self.prof_a, self.org)

        self.assertEqual(payload['resumo']['pendencias_registro'], 1)
        self.assertEqual(payload['resumo']['ofertas_trimestre'], '25.50')
        self.assertEqual(payload['resumo']['visitantes_trimestre'], 3)
        self.assertEqual(payload['ultimo_registro']['licao_numero'], 2)
        self.assertEqual(len(payload['evolucao_frequencia']), 2)
        self.assertEqual(payload['licoes_pendentes'][0]['id'], draft_lesson.id)

        scheduled = payload['aulas_escaladas'][0]
        self.assertEqual(scheduled['id'], draft_lesson.id)
        self.assertFalse(scheduled['registrada'])
        self.assertEqual(scheduled['presentes'], 0)
        self.assertEqual(scheduled['ausentes'], 0)

        ranking = {item['nome']: item for item in payload['ranking_alunos']}
        self.assertEqual(ranking['Aluno Presente']['presencas'], 2)
        self.assertEqual(ranking['Aluno Presente']['ausencias'], 0)
        self.assertEqual(ranking['Aluno Faltoso']['presencas'], 0)
        self.assertEqual(ranking['Aluno Faltoso']['ausencias'], 2)

    def test_today_lessons_include_every_linked_class(self):
        ClassTeacher.objects.create(class_group=self.turma_b, user=self.prof_a)
        today = timezone.localdate()
        today_lesson = Lesson.objects.create(
            organization=self.org,
            numero=4,
            tema='Lição de todas as turmas',
            data=today,
            revista='Revista',
            trimestre=1,
            ano=2026,
        )
        AttendanceSheet.objects.create(
            lesson=today_lesson,
            class_group=self.turma_b,
            professor=self.prof_a,
            finalized_at=timezone.now(),
        )

        payload = build_professor_dashboard(
            self.prof_a,
            self.org,
            class_id=self.turma_a.id,
        )

        self.assertEqual(
            payload['licoes_hoje'],
            [
                {
                    'id': today_lesson.id,
                    'numero': 4,
                    'tema': 'Lição de todas as turmas',
                    'data': today,
                    'trimestre': 1,
                    'ano': 2026,
                    'turma_id': self.turma_a.id,
                    'turma_nome': 'Adultos',
                    'registrada': False,
                },
                {
                    'id': today_lesson.id,
                    'numero': 4,
                    'tema': 'Lição de todas as turmas',
                    'data': today,
                    'trimestre': 1,
                    'ano': 2026,
                    'turma_id': self.turma_b.id,
                    'turma_nome': 'Jovens',
                    'registrada': True,
                },
            ],
        )

    def test_scheduled_lessons_return_aggregated_attendance_totals(self):
        for lesson in (self.lesson_1, self.lesson_2):
            LessonSchedule.objects.create(
                organization=self.org,
                lesson=lesson,
                class_group=self.turma_a,
                professor=self.prof_a,
            )

        payload = build_professor_dashboard(self.prof_a, self.org)

        self.assertEqual(len(payload['aulas_escaladas']), 2)
        self.assertTrue(
            all(item['presentes'] == 1 for item in payload['aulas_escaladas'])
        )
        self.assertTrue(
            all(item['ausentes'] == 1 for item in payload['aulas_escaladas'])
        )
        self.assertEqual(
            [(item['presentes'], item['ausentes']) for item in payload['evolucao_frequencia']],
            [(1, 1), (1, 1)],
        )

    def test_dashboard_query_count_does_not_grow_with_sheets_and_schedules(self):
        for lesson in (self.lesson_1, self.lesson_2):
            LessonSchedule.objects.create(
                organization=self.org,
                lesson=lesson,
                class_group=self.turma_a,
                professor=self.prof_a,
            )

        with CaptureQueriesContext(connection) as initial_queries:
            initial_payload = build_professor_dashboard(self.prof_a, self.org)

        for numero in range(4, 12):
            lesson = Lesson.objects.create(
                organization=self.org,
                numero=numero,
                tema=f'Lição {numero}',
                data=date.today() + timedelta(days=20 + numero),
                revista='Revista',
                trimestre=1,
                ano=2026,
            )
            sheet = AttendanceSheet.objects.create(
                lesson=lesson,
                class_group=self.turma_a,
                professor=self.prof_a,
                finalized_at=timezone.now(),
            )
            AttendanceRecord.objects.create(
                attendance_sheet=sheet,
                student=self.aluno_presente,
                presente=True,
            )
            AttendanceRecord.objects.create(
                attendance_sheet=sheet,
                student=self.aluno_faltoso,
                presente=False,
            )
            LessonSchedule.objects.create(
                organization=self.org,
                lesson=lesson,
                class_group=self.turma_a,
                professor=self.prof_a,
            )

        with CaptureQueriesContext(connection) as many_queries:
            many_payload = build_professor_dashboard(self.prof_a, self.org)

        self.assertEqual(len(initial_payload['aulas_escaladas']), 2)
        self.assertEqual(len(many_payload['aulas_escaladas']), 10)
        self.assertTrue(
            all(item['presentes'] == 1 for item in many_payload['aulas_escaladas'])
        )
        self.assertTrue(
            all(item['ausentes'] == 1 for item in many_payload['aulas_escaladas'])
        )
        self.assertLessEqual(len(many_queries), len(initial_queries) + 1)

    def test_professor_cannot_access_other_class(self):
        self._login('prof.adultos@test.com')
        response = self.client.get(f'/api/v1/dashboard/professor?class_id={self.turma_b.id}')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_today_lesson_is_actionable_without_professor_schedule(self):
        today = timezone.localdate()
        Trimester.objects.create(
            organization=self.org,
            numero=2,
            ano=2026,
            titulo='2º Trimestre 2026',
            status='PLANEJADO',
        )
        today_lesson = Lesson.objects.create(
            organization=self.org,
            numero=4,
            tema='Aula de hoje sem escala',
            data=today,
            revista='Revista',
            trimestre=2,
            ano=2026,
        )
        self.assertFalse(
            LessonSchedule.objects.filter(
                lesson=today_lesson,
                professor=self.prof_a,
            ).exists()
        )
        self._login('prof.adultos@test.com')

        dashboard_response = self.client.get('/api/v1/dashboard/professor')

        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            dashboard_response.data['licoes_hoje'],
            [
                {
                    'id': today_lesson.id,
                    'numero': 4,
                    'tema': 'Aula de hoje sem escala',
                    'data': today,
                    'trimestre': 2,
                    'ano': 2026,
                    'turma_id': self.turma_a.id,
                    'turma_nome': self.turma_a.nome,
                    'registrada': False,
                }
            ],
        )

        lessons_response = self.client.get(
            f'/api/v1/classes/{self.turma_a.id}/lessons/?trimestre=2&ano=2026'
        )
        self.assertEqual(lessons_response.status_code, status.HTTP_200_OK)
        self.assertIn(today_lesson.id, [lesson['id'] for lesson in lessons_response.data])

        attendance_response = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': today_lesson.id,
                'class_group': self.turma_a.id,
                'visitantes': 0,
                'biblias': 0,
                'revistas': 0,
                'oferta_valor': '0.00',
            },
            format='json',
        )
        self.assertEqual(attendance_response.status_code, status.HTTP_201_CREATED)

        draft_dashboard = self.client.get('/api/v1/dashboard/professor')
        self.assertFalse(draft_dashboard.data['licoes_hoje'][0]['registrada'])

        conclude_response = self.client.put(
            (
                f'/api/v1/lessons/{today_lesson.id}/classes/'
                f'{self.turma_a.id}/attendance'
            ),
            {
                'status': 'CONCLUIDA',
                'professor': self.prof_a.id,
                'records': [
                    {'student': self.aluno_presente.id, 'presente': True},
                    {'student': self.aluno_faltoso.id, 'presente': False},
                ],
            },
            format='json',
        )
        self.assertEqual(conclude_response.status_code, status.HTTP_200_OK)

        completed_dashboard = self.client.get('/api/v1/dashboard/professor')
        self.assertTrue(completed_dashboard.data['licoes_hoje'][0]['registrada'])

    def test_non_professor_gets_forbidden(self):
        self._login('sec@test.com')
        response = self.client.get('/api/v1/dashboard/professor')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_professors_do_not_leak_data(self):
        self._login('prof.jovens@test.com')
        response = self.client.get('/api/v1/dashboard/professor')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['turma']['nome'], 'Jovens')
        self.assertEqual(response.data['turma']['total_alunos'], 1)
        self.assertEqual(response.data['resumo']['pendencias_registro'], 2)
        self.assertEqual(response.data['ultimo_registro'], None)
        self.assertEqual(response.data['ranking_alunos'], [])

    def test_attendance_evolution_filtered_for_professor(self):
        self._login('prof.adultos@test.com')
        response = self.client.get('/api/v1/dashboard/attendance-evolution')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_invalid_class_id_returns_bad_request(self):
        self._login('prof.adultos@test.com')
        response = self.client.get('/api/v1/dashboard/professor?class_id=abc')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_summary_returns_visitors_total(self):
        self._login('sec@test.com')
        response = self.client.get('/api/v1/dashboard/summary')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_visitors'], 3)

    def test_general_dashboard_ignores_draft_sheet(self):
        draft_lesson = Lesson.objects.create(
            organization=self.org,
            numero=4,
            tema='Rascunho fora dos indicadores',
            data=timezone.localdate(),
            revista='Revista',
            trimestre=1,
            ano=2026,
        )
        draft_sheet = AttendanceSheet.objects.create(
            lesson=draft_lesson,
            class_group=self.turma_a,
            professor=self.prof_a,
            visitantes=50,
            oferta_valor='999.00',
            finalized_at=None,
        )
        AttendanceRecord.objects.create(
            attendance_sheet=draft_sheet,
            student=self.aluno_presente,
            presente=False,
        )
        self._login('sec@test.com')

        summary_response = self.client.get('/api/v1/dashboard/summary')
        evolution_response = self.client.get(
            '/api/v1/dashboard/attendance-evolution'
        )

        self.assertEqual(summary_response.status_code, status.HTTP_200_OK)
        self.assertEqual(summary_response.data['total_visitors'], 3)
        self.assertEqual(
            summary_response.data['attendance'],
            {'presentes': 2, 'ausentes': 2},
        )
        self.assertEqual(len(evolution_response.data), 2)

    def test_february_29_birthday_uses_february_28_in_non_leap_year(self):
        leap_student = Student.objects.create(
            organization=self.org,
            class_group=self.turma_a,
            nome='Aniversariante bissexto',
            sexo='F',
            data_nascimento=date(2000, 2, 29),
            ativo=True,
        )

        payload = _build_aniversariantes(
            Student.objects.filter(pk=leap_student.pk),
            today=date(2025, 2, 28),
            horizon_days=0,
        )

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['data'], date(2025, 2, 28))

        self._login('sec@test.com')
        response = self.client.get('/api/v1/dashboard/birthdays')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_professor_ranking_returns_aggregated_data(self):
        self._login('sec@test.com')
        response = self.client.get('/api/v1/dashboard/professor-ranking?ano=2026&trimestre=1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row['professorNome'], 'Prof Adultos')
        self.assertEqual(row['presencas'], 2)
        self.assertEqual(row['ausencias'], 0)
        self.assertEqual(row['turmaNomes'], ['Adultos'])

    def test_professor_ranking_counts_professor_once_per_lesson_across_classes(self):
        ClassTeacher.objects.create(
            class_group=self.turma_b,
            user=self.prof_a,
        )
        AttendanceSheet.objects.create(
            lesson=self.lesson_1,
            class_group=self.turma_b,
            professor=self.prof_a,
            professor_presente=True,
            finalized_at=timezone.now(),
        )
        self._login('sec@test.com')

        response = self.client.get(
            '/api/v1/dashboard/professor-ranking?ano=2026&trimestre=1'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = next(
            item
            for item in response.data
            if item['professorId'] == self.prof_a.id
        )
        self.assertEqual(row['presencas'], 2)
        self.assertEqual(row['ausencias'], 0)
        self.assertEqual(row['totalRegistros'], 2)
        self.assertEqual(set(row['turmaNomes']), {'Adultos', 'Jovens'})
