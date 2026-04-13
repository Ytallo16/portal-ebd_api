from django.conf import settings
from django.db import models

from core.models import AuditModel, OrganizationScopedModel, SoftDeleteModel


class ClassGroup(AuditModel, OrganizationScopedModel, SoftDeleteModel):
    nome = models.CharField(max_length=150)
    faixa_etaria = models.CharField(max_length=80)
    cor = models.CharField(max_length=20, default='#3B82F6')
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ['nome']
        unique_together = ('organization', 'nome')

    def __str__(self):
        return self.nome


class ClassTeacher(AuditModel):
    class_group = models.ForeignKey(ClassGroup, on_delete=models.CASCADE, related_name='teachers')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teaching_classes')

    class Meta:
        unique_together = ('class_group', 'user')
