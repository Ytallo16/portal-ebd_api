from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from lessons.attachments import MAX_ATTACHMENT_BYTES, validate_attachment_file


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


import shutil
import tempfile
from datetime import date

from django.test import TestCase, override_settings

from lessons.models import Lesson, LessonAttachment
from organizations.models import Organization


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
