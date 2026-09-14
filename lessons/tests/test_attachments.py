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
