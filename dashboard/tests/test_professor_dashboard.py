from datetime import date, timedelta

from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from attendance.models import AttendanceRecord, AttendanceSheet
from classrooms.models import ClassGroup, ClassTeacher
from lessons.models import Lesson, Trimester
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

        sheet_1 = AttendanceSheet.objects.create(
            lesson=self.lesson_1,
            class_group=self.turma_a,
            professor=self.prof_a,
            visitantes=1,
            biblias=5,
            revistas=4,
            oferta_valor='10.00',
        )
        AttendanceRecord.objects.create(
            attendance_sheet=sheet_1,
            student=self.aluno_presente,
            presente=True,
        )
        AttendanceRecord.objects.create(
            attendance_sheet=sheet_1,
            student=self.aluno_faltoso,
            presente=False,
        )

        sheet_2 = AttendanceSheet.objects.create(
            lesson=self.lesson_2,
            class_group=self.turma_a,
            professor=self.prof_a,
            visitantes=2,
            biblias=6,
            revistas=5,
            oferta_valor='15.50',
        )
        AttendanceRecord.objects.create(
            attendance_sheet=sheet_2,
            student=self.aluno_presente,
            presente=True,
        )
        AttendanceRecord.objects.create(
            attendance_sheet=sheet_2,
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
        self.assertEqual(response.data['resumo']['pendencias_registro'], 1)
        self.assertEqual(len(response.data['licoes_pendentes']), 1)
        self.assertEqual(response.data['licoes_pendentes'][0]['numero'], 3)
        self.assertEqual(len(response.data['evolucao_frequencia']), 2)
        self.assertEqual(response.data['ultimo_registro']['licao_numero'], 2)
        ranking = {item['nome']: item for item in response.data['ranking_alunos']}
        self.assertEqual(len(ranking), 2)
        self.assertEqual(ranking['Aluno Faltoso']['ausencias'], 2)
        self.assertEqual(ranking['Aluno Presente']['presencas'], 2)

    def test_professor_cannot_access_other_class(self):
        self._login('prof.adultos@test.com')
        response = self.client.get(f'/api/v1/dashboard/professor?class_id={self.turma_b.id}')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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
        self.assertEqual(response.data['resumo']['pendencias_registro'], 3)
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
