from django.core.exceptions import ValidationError
from django.db import models

from core.models import AuditModel, OrganizationScopedModel, SoftDeleteModel


class Offering(AuditModel, OrganizationScopedModel, SoftDeleteModel):
    lesson = models.ForeignKey('lessons.Lesson', on_delete=models.SET_NULL, null=True, blank=True)
    class_group = models.ForeignKey('classrooms.ClassGroup', on_delete=models.SET_NULL, null=True, blank=True)
    data = models.DateField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['-data']

    def clean(self):
        if self.valor < 0:
            raise ValidationError('Oferta não pode ser negativa.')
