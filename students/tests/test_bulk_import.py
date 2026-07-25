from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from classrooms.models import ClassGroup, ClassTeacher
from organizations.constants import TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership
from students.models import Student


class StudentBulkImportTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            nome='Igreja Importação',
            sigla='IIMP',
            tipo=TIPO_IGREJA,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.other_organization = Organization.objects.create(
            nome='Outra Igreja',
            sigla='OUT',
            tipo=TIPO_IGREJA,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.user = User.objects.create_user(
            email='secretaria.import@test.com',
            password='123456',
            nome='Secretária',
        )
        OrganizationMembership.objects.create(
            user=self.user,
            organization=self.organization,
            ativo=True,
        )
        role = Role.objects.create(nome='SECRETARIO_IGREJA')
        permission = ModulePermission.objects.create(
            modulo='alunos',
            visualizar=True,
            criar=True,
            editar=True,
            excluir=True,
            aprovar=True,
        )
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(
            user=self.user,
            role=role,
            organization=self.organization,
            ativo=True,
        )
        self.adults = ClassGroup.objects.create(
            organization=self.organization,
            nome='Adultos',
            faixa_etaria='18+',
        )
        self.young = ClassGroup.objects.create(
            organization=self.organization,
            nome='Jovens',
            faixa_etaria='15-25',
        )
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.organization.id))

    @staticmethod
    def csv_file(content):
        return SimpleUploadedFile(
            'alunos.csv',
            content.encode('utf-8'),
            content_type='text/csv',
        )

    def test_imports_valid_rows_and_reports_every_rejected_row(self):
        Student.objects.create(
            organization=self.organization,
            class_group=self.adults,
            nome='Aluno Existente',
            sexo='M',
            data_nascimento='1990-01-01',
        )
        content = (
            'nome;sexo;data_nascimento;turma;email;coluna_extra\n'
            'Maria Silva;F;15/03/1992;Adultos;maria@example.com;ignorada\n'
            'Sem Turma;M;2001-10-20;Inexistente;;ignorada\n'
            'Aluno Existente;M;1990-01-01;Adultos;;ignorada\n'
            'Data Inválida;F;31/02/2000;Jovens;;ignorada\n'
        )

        response = self.client.post(
            '/api/v1/students/import/',
            {'arquivo': self.csv_file(content)},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['fase'], 'VALIDACAO')
        self.assertEqual(response.data['total_linhas'], 4)
        self.assertEqual(response.data['validos'], 1)
        self.assertEqual(response.data['invalidos'], 3)
        self.assertEqual(response.data['cadastrados'], 0)
        self.assertEqual(response.data['nao_cadastrados'], 3)
        self.assertEqual(response.data['colunas_ignoradas'], ['coluna_extra'])
        self.assertEqual(response.data['resultados'][0]['linha'], 2)
        self.assertEqual(response.data['resultados'][0]['status'], 'VALIDO')
        self.assertFalse(Student.objects.filter(nome='Maria Silva').exists())

        confirm = self.client.post(
            f"/api/v1/students/import/{response.data['lote_id']}/confirm/",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        self.assertEqual(confirm.data['fase'], 'CONFIRMACAO')
        self.assertEqual(confirm.data['cadastrados'], 1)
        rejected_reasons = [
            reason
            for item in confirm.data['resultados']
            if item['status'] in ('INVALIDO', 'NAO_CADASTRADO')
            for reason in item['motivos']
        ]
        self.assertTrue(any('não encontrada' in reason for reason in rejected_reasons))
        self.assertTrue(any('já existe' in reason for reason in rejected_reasons))
        self.assertTrue(any('AAAA-MM-DD' in reason for reason in rejected_reasons))
        self.assertTrue(
            Student.objects.filter(
                organization=self.organization,
                nome='Maria Silva',
                class_group=self.adults,
            ).exists()
        )

    def test_missing_required_columns_returns_file_assessment_without_writes(self):
        response = self.client.post(
            '/api/v1/students/import/',
            {'arquivo': self.csv_file('nome;sexo\nMaria;F\n')},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['colunas_ausentes'],
            ['data_nascimento', 'turma'],
        )
        self.assertEqual(response.data['cadastrados'], 0)
        self.assertTrue(response.data['erros_arquivo'])

    def test_professor_can_only_import_into_an_assigned_class(self):
        professor = User.objects.create_user(
            email='prof.import@test.com',
            password='123456',
            nome='Professor',
        )
        OrganizationMembership.objects.create(
            user=professor,
            organization=self.organization,
            ativo=True,
        )
        professor_role = Role.objects.create(nome='PROFESSOR')
        permission = ModulePermission.objects.get(modulo='alunos')
        RolePermission.objects.create(role=professor_role, permission=permission)
        UserRole.objects.create(
            user=professor,
            role=professor_role,
            organization=self.organization,
            ativo=True,
        )
        ClassTeacher.objects.create(class_group=self.young, user=professor)
        self.client.force_authenticate(professor)

        content = (
            'nome,sexo,data_nascimento,turma\n'
            'Permitido,F,2000-02-02,Jovens\n'
            'Bloqueado,M,1990-01-01,Adultos\n'
        )
        response = self.client.post(
            '/api/v1/students/import/',
            {'arquivo': self.csv_file(content)},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['validos'], 1)
        self.assertEqual(response.data['nao_cadastrados'], 1)
        self.assertFalse(Student.objects.filter(nome='Bloqueado').exists())
        confirm = self.client.post(
            f"/api/v1/students/import/{response.data['lote_id']}/confirm/",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        self.assertEqual(confirm.data['cadastrados'], 1)
        self.assertFalse(Student.objects.filter(nome='Bloqueado').exists())

    def test_confirmation_is_idempotent_and_import_can_be_undone_without_hard_delete(self):
        validation = self.client.post(
            '/api/v1/students/import/',
            {
                'arquivo': self.csv_file(
                    'nome;sexo;data_nascimento;turma\n'
                    'Aluno do lote;M;2000-01-01;Adultos\n'
                )
            },
            format='multipart',
        )
        lote_id = validation.data['lote_id']

        first = self.client.post(f'/api/v1/students/import/{lote_id}/confirm/')
        second = self.client.post(f'/api/v1/students/import/{lote_id}/confirm/')
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(Student.objects.filter(nome='Aluno do lote').count(), 1)

        undo = self.client.post(f'/api/v1/students/import/{lote_id}/undo/')
        self.assertEqual(undo.status_code, status.HTTP_200_OK)
        self.assertEqual(undo.data['status_lote'], 'UNDONE')
        self.assertEqual(undo.data['desativados'], 1)
        student = Student.objects.get(nome='Aluno do lote')
        self.assertFalse(student.is_active)
        self.assertIsNotNone(student.deleted_at)
        self.assertTrue(student.historico.filter(action='IMPORT_UNDONE').exists())

    def test_undo_skips_student_changed_after_import(self):
        validation = self.client.post(
            '/api/v1/students/import/',
            {
                'arquivo': self.csv_file(
                    'nome;sexo;data_nascimento;turma\n'
                    'Aluno alterado;F;2002-02-02;Adultos\n'
                )
            },
            format='multipart',
        )
        lote_id = validation.data['lote_id']
        self.client.post(f'/api/v1/students/import/{lote_id}/confirm/')
        student = Student.objects.get(nome='Aluno alterado')
        student.telefone = '9999-9999'
        student.save(update_fields=['telefone', 'updated_at'])

        undo = self.client.post(f'/api/v1/students/import/{lote_id}/undo/')
        self.assertEqual(undo.status_code, status.HTTP_200_OK)
        self.assertEqual(undo.data['status_lote'], 'PARTIALLY_UNDONE')
        self.assertEqual(undo.data['nao_desfeitos'], 1)
        student.refresh_from_db()
        self.assertTrue(student.is_active)
        self.assertIn(
            'alterado após a importação',
            undo.data['resultados'][0]['motivos'][0],
        )

    def test_import_history_is_scoped_to_active_organization(self):
        response = self.client.post(
            '/api/v1/students/import/',
            {
                'arquivo': self.csv_file(
                    'nome;sexo;data_nascimento;turma\n'
                    'Histórico;M;2000-01-01;Adultos\n'
                )
            },
            format='multipart',
        )
        history = self.client.get('/api/v1/students/imports/')
        self.assertEqual(history.status_code, status.HTTP_200_OK)
        self.assertEqual(history.data['count'], 1)
        self.assertEqual(history.data['results'][0]['lote_id'], response.data['lote_id'])

    def test_regular_create_rejects_class_from_another_organization(self):
        foreign_class = ClassGroup.objects.create(
            organization=self.other_organization,
            nome='Estrangeira',
            faixa_etaria='18+',
        )
        response = self.client.post(
            '/api/v1/students/',
            {
                'class_group': foreign_class.id,
                'nome': 'Aluno Indevido',
                'sexo': 'M',
                'data_nascimento': '2000-01-01',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('class_group', response.data)
