import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from core.models import AuditModel, OrganizationScopedModel, SoftDeleteModel


class Trimester(AuditModel, OrganizationScopedModel, SoftDeleteModel):
    STATUS_CHOICES = [('PLANEJADO', 'Planejado'), ('EM_ANDAMENTO', 'Em andamento'), ('ENCERRADO', 'Encerrado')]

    numero = models.PositiveSmallIntegerField()
    ano = models.PositiveIntegerField()
    titulo = models.CharField(max_length=120, blank=True)
    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)
    quantidade_licoes = models.PositiveSmallIntegerField(default=13)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANEJADO')

    class Meta:
        ordering = ['-ano', '-numero']
        unique_together = ('organization', 'ano', 'numero')

    def __str__(self):
        return f'{self.numero}º Trimestre {self.ano}'


class Lesson(AuditModel, OrganizationScopedModel, SoftDeleteModel):
    STATUS_CHOICES = [('ABERTA', 'Aberta'), ('FINALIZADA', 'Finalizada')]

    numero = models.PositiveIntegerField()
    tema = models.CharField(max_length=255)
    data = models.DateField()
    revista = models.CharField(max_length=255)
    texto_aureo = models.CharField(max_length=255, blank=True)
    texto_biblico = models.TextField(blank=True)
    objetivo = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ABERTA')
    trimestre = models.PositiveSmallIntegerField()
    ano = models.PositiveIntegerField()

    class Meta:
        ordering = ['-data', 'numero']
        unique_together = ('organization', 'trimestre', 'ano', 'numero')

    def __str__(self):
        return f'Lição {self.numero} - {self.tema}'


class LessonSchedule(AuditModel, OrganizationScopedModel):
    """Escala: professor designado para ministrar uma lição em uma turma."""

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='schedules')
    class_group = models.ForeignKey(
        'classrooms.ClassGroup',
        on_delete=models.CASCADE,
        related_name='lesson_schedules',
    )
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lesson_schedules',
    )

    class Meta:
        ordering = ['lesson__data', 'class_group__nome']
        unique_together = ('lesson', 'class_group')

    def __str__(self):
        prof = self.professor.nome if self.professor_id else '—'
        return f'{self.class_group.nome} · Lição {self.lesson.numero} · {prof}'


def lesson_attachment_path(instance, filename):
    """Nome randômico: a pasta /media/ é servida publicamente pelo nginx."""
    extensao = Path(filename or '').suffix.lower()[:10]
    return f'licoes/anexos/{instance.lesson_id}/{uuid.uuid4().hex}{extensao}'


class LessonAttachment(AuditModel, OrganizationScopedModel, SoftDeleteModel):
    """Material de apoio anexado a uma lição (plano de aula, slides, áudio)."""

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='attachments')
    arquivo = models.FileField(upload_to=lesson_attachment_path)
    nome_original = models.CharField(max_length=255)
    descricao = models.CharField(max_length=255, blank=True)
    tamanho = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['lesson', 'is_active']),
        ]

    def __str__(self):
        return f'{self.nome_original} · Lição {self.lesson.numero}'
