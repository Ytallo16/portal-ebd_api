from django.db import models

from core.models import AuditModel, OrganizationScopedModel, SoftDeleteModel

from .constants import PAYMENT_METHOD_CHOICES


class PublicationControl(AuditModel, OrganizationScopedModel, SoftDeleteModel):
    PERSON_TYPE_CHOICES = [('professor', 'Professor'), ('aluno', 'Aluno')]

    trimester = models.ForeignKey(
        'lessons.Trimester',
        on_delete=models.CASCADE,
        related_name='publication_controls',
    )
    class_group = models.ForeignKey('classrooms.ClassGroup', on_delete=models.CASCADE, related_name='publication_controls')
    person_type = models.CharField(max_length=20, choices=PERSON_TYPE_CHOICES)
    person_name = models.CharField(max_length=255)
    student = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True)
    professor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    recebeu = models.BooleanField(default=False)
    pagou = models.BooleanField(default=False)
    metodo_pagamento = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, default='')

    class Meta:
        ordering = ['person_name']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'class_group', 'student', 'trimester'],
                condition=models.Q(student__isnull=False),
                name='uniq_pubcontrol_student_trimester',
            ),
            models.UniqueConstraint(
                fields=['organization', 'class_group', 'professor', 'trimester'],
                condition=models.Q(professor__isnull=False),
                name='uniq_pubcontrol_professor_trimester',
            ),
        ]
