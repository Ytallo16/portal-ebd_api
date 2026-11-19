from django.conf import settings
from django.db import models

from core.models import AuditModel


class AttendanceSheet(AuditModel):
    STATUS_RASCUNHO = 'RASCUNHO'
    STATUS_CONCLUIDA = 'CONCLUIDA'

    lesson = models.ForeignKey('lessons.Lesson', on_delete=models.CASCADE, related_name='attendance_sheets')
    class_group = models.ForeignKey('classrooms.ClassGroup', on_delete=models.CASCADE, related_name='attendance_sheets')
    professor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    professor_presente = models.BooleanField(default=False)
    visitantes = models.PositiveIntegerField(default=0)
    biblias = models.PositiveIntegerField(default=0)
    revistas = models.PositiveIntegerField(default=0)
    oferta_valor = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('lesson', 'class_group')
        # Sem ordenação explícita a paginação do DRF repete/perde fichas
        # entre páginas.
        ordering = ['lesson__numero', 'class_group__nome', 'id']

    @property
    def status(self):
        return self.STATUS_CONCLUIDA if self.finalized_at else self.STATUS_RASCUNHO


class AttendanceTeacher(AuditModel):
    """Presença de cada professor da turma na lição.

    `AttendanceSheet.professor` continua indicando quem ministrou a lição;
    aqui ficam as presenças, uma linha por professor, porque uma turma pode
    ter mais de um professor na mesma lição.
    """

    attendance_sheet = models.ForeignKey(
        AttendanceSheet,
        on_delete=models.CASCADE,
        related_name='teachers',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_presences',
    )
    presente = models.BooleanField(default=False)

    class Meta:
        unique_together = ('attendance_sheet', 'user')
        ordering = ['user__nome']


class AttendanceRecord(AuditModel):
    attendance_sheet = models.ForeignKey(AttendanceSheet, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)
    presente = models.BooleanField(default=False)

    class Meta:
        unique_together = ('attendance_sheet', 'student')
