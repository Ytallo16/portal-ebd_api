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
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'lesson', 'class_group'],
                condition=models.Q(
                    is_active=True,
                    lesson__isnull=False,
                    class_group__isnull=False,
                ),
                name='uniq_active_offering_lesson_class',
            ),
        ]

    def clean(self):
        if self.valor < 0:
            raise ValidationError('Oferta não pode ser negativa.')
