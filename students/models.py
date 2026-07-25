import uuid

from django.conf import settings
from django.db import models

from core.models import AuditModel, OrganizationScopedModel, SoftDeleteModel


class Student(AuditModel, OrganizationScopedModel, SoftDeleteModel):
    SEXO_CHOICES = [('M', 'Masculino'), ('F', 'Feminino')]

    class_group = models.ForeignKey(
        'classrooms.ClassGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
    )
    nome = models.CharField(max_length=255)
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    data_nascimento = models.DateField()
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nome']


class StudentAddress(AuditModel):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='endereco')
    cep = models.CharField(max_length=12, blank=True)
    rua = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=30, blank=True)
    complemento = models.CharField(max_length=255, blank=True)
    bairro = models.CharField(max_length=120, blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    uf = models.CharField(max_length=2, blank=True)


class StudentGuardian(AuditModel):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='responsaveis')
    nome = models.CharField(max_length=255)
    telefone = models.CharField(max_length=30, blank=True)


class StudentHistory(models.Model):
    ACTION_CREATED = 'CREATED'
    ACTION_UPDATED = 'UPDATED'
    ACTION_DEACTIVATED = 'DEACTIVATED'
    ACTION_RESTORED = 'RESTORED'
    ACTION_IMPORTED = 'IMPORTED'
    ACTION_IMPORT_UNDONE = 'IMPORT_UNDONE'
    ACTION_CHOICES = (
        (ACTION_CREATED, 'Criado'),
        (ACTION_UPDATED, 'Atualizado'),
        (ACTION_DEACTIVATED, 'Inativado'),
        (ACTION_RESTORED, 'Restaurado'),
        (ACTION_IMPORTED, 'Importado'),
        (ACTION_IMPORT_UNDONE, 'Importação desfeita'),
    )

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='historico')
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_history_events',
    )
    changes = models.JSONField(default=dict, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['student', '-created_at']),
            models.Index(fields=['organization', '-created_at']),
        ]


class StudentImportBatch(AuditModel, OrganizationScopedModel):
    STATUS_INVALID = 'INVALID'
    STATUS_VALIDATED = 'VALIDATED'
    STATUS_CONFIRMED = 'CONFIRMED'
    STATUS_UNDONE = 'UNDONE'
    STATUS_PARTIALLY_UNDONE = 'PARTIALLY_UNDONE'
    STATUS_CHOICES = (
        (STATUS_INVALID, 'Inválido'),
        (STATUS_VALIDATED, 'Validado'),
        (STATUS_CONFIRMED, 'Confirmado'),
        (STATUS_UNDONE, 'Desfeito'),
        (STATUS_PARTIALLY_UNDONE, 'Parcialmente desfeito'),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    original_filename = models.CharField(max_length=255)
    file_sha256 = models.CharField(max_length=64)
    file_size = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    invalid_rows = models.PositiveIntegerField(default=0)
    created_students = models.PositiveIntegerField(default=0)
    ignored_columns = models.JSONField(default=list, blank=True)
    missing_columns = models.JSONField(default=list, blank=True)
    file_errors = models.JSONField(default=list, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_imports_confirmed',
    )
    undone_at = models.DateTimeField(null=True, blank=True)
    undone_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_imports_undone',
    )

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['organization', 'status']),
        ]


class StudentImportRow(models.Model):
    STATUS_VALID = 'VALID'
    STATUS_INVALID = 'INVALID'
    STATUS_CREATED = 'CREATED'
    STATUS_FAILED = 'FAILED'
    STATUS_UNDONE = 'UNDONE'
    STATUS_UNDO_SKIPPED = 'UNDO_SKIPPED'
    STATUS_CHOICES = (
        (STATUS_VALID, 'Válido'),
        (STATUS_INVALID, 'Inválido'),
        (STATUS_CREATED, 'Criado'),
        (STATUS_FAILED, 'Falhou ao confirmar'),
        (STATUS_UNDONE, 'Desfeito'),
        (STATUS_UNDO_SKIPPED, 'Não desfeito'),
    )

    batch = models.ForeignKey(
        StudentImportBatch,
        on_delete=models.CASCADE,
        related_name='rows',
    )
    row_number = models.PositiveIntegerField()
    name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)
    student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_rows',
    )
    student_version_at_confirm = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['row_number', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['batch', 'row_number'],
                name='unique_student_import_batch_row',
            ),
        ]
