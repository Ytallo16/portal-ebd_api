from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from access_control.constants import ROLE_PROFESSOR
from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from attendance.models import AttendanceSheet, AttendanceTeacher
from classrooms.models import ClassGroup, ClassTeacher
from lessons.models import Lesson
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership
from students.models import Student


class TeacherAttendanceTests(APITestCase):
    """Frequência dos professores: vários professores por turma na mesma lição.

    Regressão relatada em produção (15/11/2026): marcar o segundo professor
    de uma turma apagava o registro do primeiro, porque a ficha guardava um
    único `professor` + `professor_presente`.
    """

    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo Professores',
            sigla='CPR',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.org = Organization.objects.create(
            nome='Org Professores',
            sigla='OPR',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )

        self.secretario = User.objects.create_user(
            email='sec@test.com',
            password='123456',
            nome='Secretario',
        )
        OrganizationMembership.objects.create(
            user=self.secretario,
            organization=self.org,
            ativo=True,
        )
        role = Role.objects.create(nome='ADMINISTRADOR')
        for module in ['licoes', 'frequencia', 'turmas', 'alunos', 'dashboard']:
            perm = ModulePermission.objects.create(
                modulo=module,
                visualizar=True,
                criar=True,
                editar=True,
                excluir=True,
                aprovar=True,
            )
            RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(
            user=self.secretario,
            role=role,
            organization=self.org,
            ativo=True,
        )

        self.turma = ClassGroup.objects.create(
            organization=self.org,
            nome='Adultos',
            faixa_etaria='26-35',
            created_by=self.secretario,
        )
        self.professor_role = Role.objects.create(nome=ROLE_PROFESSOR)
        self.prof_joao = self._criar_professor('joao@test.com', 'Joao', self.turma)
        self.prof_maria = self._criar_professor('maria@test.com', 'Maria', self.turma)

        self.lesson = Lesson.objects.create(
            organization=self.org,
            numero=1,
            tema='Tema',
            data=date.today(),
            revista='Revista',
            trimestre=1,
            ano=2026,
            created_by=self.secretario,
        )
        self.student = Student.objects.create(
            organization=self.org,
            class_group=self.turma,
            nome='Aluno 1',
            sexo='M',
            data_nascimento=date(2000, 1, 1),
            created_by=self.secretario,
        )

        self._login('sec@test.com')

    def _criar_professor(self, email, nome, turma):
        professor = User.objects.create_user(email=email, password='123456', nome=nome)
        OrganizationMembership.objects.create(
            user=professor,
            organization=self.org,
            ativo=True,
        )
        UserRole.objects.create(
            user=professor,
            role=self.professor_role,
            organization=self.org,
            ativo=True,
        )
        ClassTeacher.objects.create(class_group=turma, user=professor)
        return professor

    def _login(self, email):
        login = self.client.post(
            '/api/v1/auth/login',
            {'email': email, 'password': '123456'},
            format='json',
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}",
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

    def _criar_ficha(self, **overrides):
        return AttendanceSheet.objects.create(
            lesson=self.lesson,
            class_group=self.turma,
            created_by=self.secretario,
            **overrides,
        )

    def _salvar_professores(self, sheet_id, teachers):
        return self.client.post(
            f'/api/v1/attendance-sheets/{sheet_id}/teachers/',
            {'teachers': teachers},
            format='json',
        )

    # --- o bug relatado ---------------------------------------------------

    def test_dois_professores_da_mesma_turma_ficam_presentes(self):
        sheet = self._criar_ficha()

        response = self._salvar_professores(
            sheet.id,
            [
                {'user': self.prof_joao.id, 'presente': True},
                {'user': self.prof_maria.id, 'presente': True},
            ],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        presencas = dict(
            AttendanceTeacher.objects.filter(attendance_sheet=sheet).values_list(
                'user_id',
                'presente',
            )
        )
        self.assertEqual(
            presencas,
            {self.prof_joao.id: True, self.prof_maria.id: True},
        )

    def test_salvar_em_lote_nao_apaga_professor_salvo_antes(self):
        sheet = self._criar_ficha()
        self._salvar_professores(
            sheet.id,
            [{'user': self.prof_joao.id, 'presente': True}],
        )

        self._salvar_professores(
            sheet.id,
            [{'user': self.prof_maria.id, 'presente': True}],
        )

        self.assertTrue(
            AttendanceTeacher.objects.get(
                attendance_sheet=sheet,
                user=self.prof_joao,
            ).presente
        )

    def test_desmarcar_professor_persiste_como_ausente(self):
        sheet = self._criar_ficha()
        self._salvar_professores(
            sheet.id,
            [
                {'user': self.prof_joao.id, 'presente': True},
                {'user': self.prof_maria.id, 'presente': True},
            ],
        )

        response = self._salvar_professores(
            sheet.id,
            [{'user': self.prof_maria.id, 'presente': False}],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            AttendanceTeacher.objects.get(
                attendance_sheet=sheet,
                user=self.prof_maria,
            ).presente
        )
        self.assertTrue(
            AttendanceTeacher.objects.get(
                attendance_sheet=sheet,
                user=self.prof_joao,
            ).presente
        )

    def test_resposta_devolve_professores_da_ficha(self):
        sheet = self._criar_ficha()

        response = self._salvar_professores(
            sheet.id,
            [
                {'user': self.prof_joao.id, 'presente': True},
                {'user': self.prof_maria.id, 'presente': False},
            ],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        devolvidos = {
            item['user']: item['presente'] for item in response.data['teachers']
        }
        self.assertEqual(
            devolvidos,
            {self.prof_joao.id: True, self.prof_maria.id: False},
        )

    def test_listagem_de_fichas_inclui_professores(self):
        sheet = self._criar_ficha()
        self._salvar_professores(
            sheet.id,
            [{'user': self.prof_joao.id, 'presente': True}],
        )

        response = self.client.get('/api/v1/attendance-sheets/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ficha = next(
            item for item in response.data['results'] if item['id'] == sheet.id
        )
        self.assertEqual(
            [{'user': self.prof_joao.id, 'presente': True}],
            [
                {'user': item['user'], 'presente': item['presente']}
                for item in ficha['teachers']
            ],
        )

    # --- a chamada dos alunos não pode apagar a frequência ----------------

    def test_chamada_dos_alunos_nao_apaga_frequencia_dos_professores(self):
        sheet = self._criar_ficha()
        self._salvar_professores(
            sheet.id,
            [
                {'user': self.prof_joao.id, 'presente': True},
                {'user': self.prof_maria.id, 'presente': True},
            ],
        )

        response = self.client.put(
            f'/api/v1/lessons/{self.lesson.id}/classes/{self.turma.id}/attendance',
            {
                'status': 'CONCLUIDA',
                'professor': self.prof_joao.id,
                'visitantes': 2,
                'biblias': 3,
                'revistas': 4,
                'oferta_valor': '10.00',
                'records': [{'student': self.student.id, 'presente': True}],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        presencas = dict(
            AttendanceTeacher.objects.filter(attendance_sheet=sheet).values_list(
                'user_id',
                'presente',
            )
        )
        self.assertEqual(
            presencas,
            {self.prof_joao.id: True, self.prof_maria.id: True},
        )

    # --- validações -------------------------------------------------------

    def test_professor_de_outra_turma_e_rejeitado(self):
        outra_turma = ClassGroup.objects.create(
            organization=self.org,
            nome='Jovens',
            faixa_etaria='18-25',
            created_by=self.secretario,
        )
        prof_externo = self._criar_professor(
            'externo@test.com',
            'Externo',
            outra_turma,
        )
        sheet = self._criar_ficha()

        response = self._salvar_professores(
            sheet.id,
            [{'user': prof_externo.id, 'presente': True}],
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            AttendanceTeacher.objects.filter(attendance_sheet=sheet).exists()
        )

    def test_professor_repetido_no_payload_e_rejeitado(self):
        sheet = self._criar_ficha()

        response = self._salvar_professores(
            sheet.id,
            [
                {'user': self.prof_joao.id, 'presente': True},
                {'user': self.prof_joao.id, 'presente': False},
            ],
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_salvar_professores_nao_reabre_chamada_concluida(self):
        sheet = self._criar_ficha(finalized_at=timezone.now())

        response = self._salvar_professores(
            sheet.id,
            [{'user': self.prof_joao.id, 'presente': True}],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sheet.refresh_from_db()
        self.assertIsNotNone(sheet.finalized_at)

    def test_professor_so_salva_nas_turmas_em_que_leciona(self):
        outra_turma = ClassGroup.objects.create(
            organization=self.org,
            nome='Jovens',
            faixa_etaria='18-25',
            created_by=self.secretario,
        )
        prof_externo = self._criar_professor(
            'externo@test.com',
            'Externo',
            outra_turma,
        )
        sheet = self._criar_ficha()
        self._login('externo@test.com')

        response = self._salvar_professores(
            sheet.id,
            [{'user': prof_externo.id, 'presente': True}],
        )

        self.assertIn(
            response.status_code,
            {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND},
        )

    # --- filtro por lição (a tela carregava só as 20 primeiras fichas) ----

    def test_listagem_de_fichas_filtra_por_licao(self):
        outra_licao = Lesson.objects.create(
            organization=self.org,
            numero=2,
            tema='Tema 2',
            data=date.today(),
            revista='Revista',
            trimestre=1,
            ano=2026,
            created_by=self.secretario,
        )
        ficha_licao_1 = self._criar_ficha()
        AttendanceSheet.objects.create(
            lesson=outra_licao,
            class_group=self.turma,
            created_by=self.secretario,
        )

        response = self.client.get(
            f'/api/v1/attendance-sheets/?lesson={self.lesson.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item['id'] for item in response.data['results']],
            [ficha_licao_1.id],
        )


class TeacherAttendanceRankingTests(TeacherAttendanceTests):
    """O ranking do dashboard deve contar cada professor individualmente."""

    def test_ranking_conta_os_dois_professores_da_turma(self):
        sheet = self._criar_ficha(
            professor=self.prof_joao,
            finalized_at=timezone.now(),
        )
        self._salvar_professores(
            sheet.id,
            [
                {'user': self.prof_joao.id, 'presente': True},
                {'user': self.prof_maria.id, 'presente': False},
            ],
        )

        response = self.client.get(
            '/api/v1/dashboard/professor-ranking?ano=2026&trimestre=1'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        por_professor = {item['professorId']: item for item in response.data}
        self.assertEqual(por_professor[self.prof_joao.id]['presencas'], 1)
        self.assertEqual(por_professor[self.prof_joao.id]['ausencias'], 0)
        self.assertEqual(por_professor[self.prof_maria.id]['presencas'], 0)
        self.assertEqual(por_professor[self.prof_maria.id]['ausencias'], 1)

    def test_ranking_usa_campo_legado_quando_nao_ha_registro_por_professor(self):
        self._criar_ficha(
            professor=self.prof_joao,
            professor_presente=True,
            finalized_at=timezone.now(),
        )

        response = self.client.get(
            '/api/v1/dashboard/professor-ranking?ano=2026&trimestre=1'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        linha = next(
            item
            for item in response.data
            if item['professorId'] == self.prof_joao.id
        )
        self.assertEqual(linha['presencas'], 1)
        self.assertEqual(linha['ausencias'], 0)
