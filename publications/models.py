from django.db import models

from core.models import AuditModel, OrganizationScopedModel, SoftDeleteModel


class PublicationControl(AuditModel, OrganizationScopedModel, SoftDeleteModel):
    PERSON_TYPE_CHOICES = [('professor', 'Professor'), ('aluno', 'Aluno')]

    class_group = models.ForeignKey('classrooms.ClassGroup', on_delete=models.CASCADE, related_name='publication_controls')
    person_type = models.CharField(max_length=20, choices=PERSON_TYPE_CHOICES)
    person_name = models.CharField(max_length=255)
    student = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True)
    professor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    recebeu = models.BooleanField(default=False)
    pagou = models.BooleanField(default=False)

    class Meta:
        ordering = ['person_name']
