import shutil
import tempfile
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from classrooms.models import ClassGroup
from lessons.attachments import MAX_ATTACHMENT_BYTES, validate_attachment_file
from lessons.models import Lesson, LessonAttachment, LessonSchedule
from lessons.services import (
    can_delete_lesson_attachment,
    can_upload_lesson_attachment,
)
from organizations.models import Organization


class ValidateAttachmentFileTests(SimpleTestCase):
    def test_accepts_pdf_within_limit(self):
        arquivo = SimpleUploadedFile('licao.pdf', b'%PDF-1.4 conteudo', content_type='application/pdf')
        validate_attachment_file(arquivo)

    def test_rejects_disallowed_extension(self):
        arquivo = SimpleUploadedFile('malicioso.exe', b'MZ', content_type='application/octet-stream')
        with self.assertRaises(ValidationError) as ctx:
            validate_attachment_file(arquivo)
        self.assertIn('Formato não permitido', str(ctx.exception))

    def test_rejects_file_without_extension(self):
        arquivo = SimpleUploadedFile('semextensao', b'abc', content_type='text/plain')
        with self.assertRaises(ValidationError):
            validate_attachment_file(arquivo)

    def test_rejects_file_over_size_limit(self):
        grande = SimpleUploadedFile('grande.pdf', b'x' * (MAX_ATTACHMENT_BYTES + 1), content_type='application/pdf')
        with self.assertRaises(ValidationError) as ctx:
            validate_attachment_file(grande)
        self.assertIn('5 MB', str(ctx.exception))

    def test_rejects_empty_file(self):
        vazio = SimpleUploadedFile('vazio.pdf', b'', content_type='application/pdf')
        with self.assertRaises(ValidationError):
            validate_attachment_file(vazio)

    def test_extension_check_is_case_insensitive(self):
        arquivo = SimpleUploadedFile('SLIDES.PPTX', b'conteudo', content_type='application/vnd.ms-powerpoint')
        validate_attachment_file(arquivo)


class TempMediaRootMixin:
    """Isola os uploads dos testes num MEDIA_ROOT temporário.

    Sem isso os testes gravam em media/ do projeto e deixam lixo no repositório.
    """

    @classmethod
    def setUpClass(cls):
        cls._temp_media = tempfile.mkdtemp(prefix='ebd-test-media-')
        cls._media_override = override_settings(MEDIA_ROOT=cls._temp_media)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._temp_media, ignore_errors=True)


class LessonAttachmentModelTests(TempMediaRootMixin, TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            nome='AD Teste', sigla='ADT', tipo='IGREJA', formato='IGREJA_INDIVIDUAL',
            cidade='Teresina', uf='PI',
        )
        self.lesson = Lesson.objects.create(
            organization=self.org, numero=1, tema='A Criação', data=date(2026, 9, 13),
            revista='Adultos', trimestre=3, ano=2026,
        )

    def test_upload_path_uses_lesson_id_and_random_name(self):
        anexo = LessonAttachment.objects.create(
            organization=self.org,
            lesson=self.lesson,
            arquivo=SimpleUploadedFile('Plano de Aula.pdf', b'conteudo', content_type='application/pdf'),
            nome_original='Plano de Aula.pdf',
            tamanho=8,
            content_type='application/pdf',
        )
        caminho = anexo.arquivo.name
        self.assertTrue(caminho.startswith(f'licoes/anexos/{self.lesson.id}/'))
        self.assertTrue(caminho.endswith('.pdf'))
        self.assertNotIn('Plano de Aula', caminho)

    def test_related_name_attachments(self):
        LessonAttachment.objects.create(
            organization=self.org, lesson=self.lesson,
            arquivo=SimpleUploadedFile('a.pdf', b'x', content_type='application/pdf'),
            nome_original='a.pdf', tamanho=1,
        )
        self.assertEqual(self.lesson.attachments.count(), 1)

    def test_defaults_to_active(self):
        anexo = LessonAttachment.objects.create(
            organization=self.org, lesson=self.lesson,
            arquivo=SimpleUploadedFile('b.pdf', b'x', content_type='application/pdf'),
            nome_original='b.pdf', tamanho=1,
        )
        self.assertTrue(anexo.is_active)
        self.assertIsNone(anexo.deleted_at)


class LessonAttachmentPermissionTests(TempMediaRootMixin, TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            nome='AD Perm', sigla='ADP', tipo='IGREJA', formato='IGREJA_INDIVIDUAL',
            cidade='Teresina', uf='PI',
        )
        self.lesson = Lesson.objects.create(
            organization=self.org, numero=2, tema='O Dilúvio', data=date(2026, 9, 20),
            revista='Adultos', trimestre=3, ano=2026,
        )
        self.turma = ClassGroup.objects.create(
            organization=self.org, nome='Jovens', faixa_etaria='18-25',
        )
        self.role_secretario = Role.objects.create(nome='SECRETARIO_IGREJA', ativo=True)
        self.role_professor = Role.objects.create(nome='PROFESSOR', ativo=True)

        self.secretario = User.objects.create_user(
            email='sec@teste.com', password='x', nome='Secretário',
        )
        UserRole.objects.create(user=self.secretario, role=self.role_secretario, organization=self.org, ativo=True)

        self.prof_escalado = User.objects.create_user(
            email='prof1@teste.com', password='x', nome='Professor Escalado',
        )
        UserRole.objects.create(user=self.prof_escalado, role=self.role_professor, organization=self.org, ativo=True)
        LessonSchedule.objects.create(
            organization=self.org, lesson=self.lesson, class_group=self.turma, professor=self.prof_escalado,
        )

        self.prof_sem_escala = User.objects.create_user(
            email='prof2@teste.com', password='x', nome='Professor Sem Escala',
        )
        UserRole.objects.create(user=self.prof_sem_escala, role=self.role_professor, organization=self.org, ativo=True)

    def _anexo_de(self, autor):
        return LessonAttachment.objects.create(
            organization=self.org, lesson=self.lesson,
            arquivo=SimpleUploadedFile('x.pdf', b'x', content_type='application/pdf'),
            nome_original='x.pdf', tamanho=1, created_by=autor,
        )

    def test_secretario_can_upload(self):
        self.assertTrue(can_upload_lesson_attachment(self.secretario, self.lesson))

    def test_scheduled_professor_can_upload(self):
        self.assertTrue(can_upload_lesson_attachment(self.prof_escalado, self.lesson))

    def test_professor_without_schedule_cannot_upload(self):
        self.assertFalse(can_upload_lesson_attachment(self.prof_sem_escala, self.lesson))

    def test_secretario_can_delete_any_attachment(self):
        anexo = self._anexo_de(self.prof_escalado)
        self.assertTrue(can_delete_lesson_attachment(self.secretario, anexo))

    def test_professor_can_delete_own_attachment(self):
        anexo = self._anexo_de(self.prof_escalado)
        self.assertTrue(can_delete_lesson_attachment(self.prof_escalado, anexo))

    def test_professor_cannot_delete_attachment_from_someone_else(self):
        anexo = self._anexo_de(self.secretario)
        self.assertFalse(can_delete_lesson_attachment(self.prof_escalado, anexo))


class LessonAttachmentApiTests(TempMediaRootMixin, TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            nome='AD Api', sigla='ADA', tipo='IGREJA', formato='IGREJA_INDIVIDUAL',
            cidade='Teresina', uf='PI',
        )
        self.lesson = Lesson.objects.create(
            organization=self.org, numero=3, tema='Abraão', data=date(2026, 9, 27),
            revista='Adultos', trimestre=3, ano=2026,
        )
        permissao = ModulePermission.objects.create(
            modulo='licoes', visualizar=True, criar=True, editar=True, excluir=True, aprovar=True,
        )
        role = Role.objects.create(nome='SECRETARIO_IGREJA', ativo=True)
        RolePermission.objects.create(role=role, permission=permissao)

        self.secretario = User.objects.create_user(
            email='api.sec@teste.com', password='x', nome='Secretário Api',
        )
        UserRole.objects.create(user=self.secretario, role=role, organization=self.org, ativo=True)
        self.secretario.active_organization = self.org
        self.secretario.save(update_fields=['active_organization'])

        self.client = APIClient()
        self.client.force_authenticate(user=self.secretario)

    def test_upload_creates_attachment_with_metadata(self):
        arquivo = SimpleUploadedFile('Plano de Aula.pdf', b'%PDF-1.4 x' * 10, content_type='application/pdf')
        resposta = self.client.post(
            '/api/v1/lesson-attachments/',
            {'lesson': self.lesson.id, 'arquivo': arquivo, 'descricao': 'Plano da semana'},
            format='multipart',
        )
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data['nome_original'], 'Plano de Aula.pdf')
        self.assertEqual(resposta.data['descricao'], 'Plano da semana')
        self.assertGreater(resposta.data['tamanho'], 0)
        self.assertTrue(resposta.data['arquivo_url'].endswith('.pdf'))

        anexo = LessonAttachment.objects.get(id=resposta.data['id'])
        self.assertEqual(anexo.created_by, self.secretario)
        self.assertEqual(anexo.organization, self.org)

    def test_upload_rejects_disallowed_extension(self):
        arquivo = SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')
        resposta = self.client.post(
            '/api/v1/lesson-attachments/',
            {'lesson': self.lesson.id, 'arquivo': arquivo},
            format='multipart',
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(LessonAttachment.objects.count(), 0)

    def test_list_filters_by_lesson_id(self):
        outra = Lesson.objects.create(
            organization=self.org, numero=4, tema='Isaque', data=date(2026, 10, 4),
            revista='Adultos', trimestre=3, ano=2026,
        )
        for licao in (self.lesson, outra):
            LessonAttachment.objects.create(
                organization=self.org, lesson=licao,
                arquivo=SimpleUploadedFile('x.pdf', b'x', content_type='application/pdf'),
                nome_original='x.pdf', tamanho=1, created_by=self.secretario,
            )

        resposta = self.client.get(f'/api/v1/lesson-attachments/?lesson_id={self.lesson.id}')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.data['results']), 1)
        self.assertEqual(resposta.data['results'][0]['lesson'], self.lesson.id)

    def test_delete_soft_deletes(self):
        anexo = LessonAttachment.objects.create(
            organization=self.org, lesson=self.lesson,
            arquivo=SimpleUploadedFile('y.pdf', b'y', content_type='application/pdf'),
            nome_original='y.pdf', tamanho=1, created_by=self.secretario,
        )
        resposta = self.client.delete(f'/api/v1/lesson-attachments/{anexo.id}/')
        self.assertEqual(resposta.status_code, 204)

        anexo.refresh_from_db()
        self.assertFalse(anexo.is_active)
        self.assertIsNotNone(anexo.deleted_at)

    def test_deleted_attachment_disappears_from_list(self):
        anexo = LessonAttachment.objects.create(
            organization=self.org, lesson=self.lesson,
            arquivo=SimpleUploadedFile('z.pdf', b'z', content_type='application/pdf'),
            nome_original='z.pdf', tamanho=1, created_by=self.secretario,
        )
        self.client.delete(f'/api/v1/lesson-attachments/{anexo.id}/')
        resposta = self.client.get(f'/api/v1/lesson-attachments/?lesson_id={self.lesson.id}')
        self.assertEqual(len(resposta.data['results']), 0)

    def test_cannot_upload_to_lesson_of_another_organization(self):
        outra_org = Organization.objects.create(
            nome='AD Outra', sigla='ADO', tipo='IGREJA', formato='IGREJA_INDIVIDUAL',
            cidade='Parnaíba', uf='PI',
        )
        licao_alheia = Lesson.objects.create(
            organization=outra_org, numero=1, tema='Alheia', data=date(2026, 9, 13),
            revista='Adultos', trimestre=3, ano=2026,
        )
        arquivo = SimpleUploadedFile('a.pdf', b'x', content_type='application/pdf')
        resposta = self.client.post(
            '/api/v1/lesson-attachments/',
            {'lesson': licao_alheia.id, 'arquivo': arquivo},
            format='multipart',
        )
        self.assertIn(resposta.status_code, (400, 403))
        self.assertEqual(LessonAttachment.objects.count(), 0)
