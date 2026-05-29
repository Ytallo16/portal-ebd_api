from django.conf import settings
from django.db import models

from core.models import AuditModel, SoftDeleteModel

from .constants import (
    FORMATO_CAMPO,
    FORMATO_CHOICES,
    FORMATO_IGREJA_INDIVIDUAL,
    TIPO_CAMPO,
    TIPO_CHOICES,
    TIPO_IGREJA,
)


class Organization(AuditModel, SoftDeleteModel):
    nome = models.CharField(max_length=255)
    sigla = models.CharField(max_length=50)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    formato = models.CharField(max_length=20, choices=FORMATO_CHOICES, blank=True, default='')
    cidade = models.CharField(max_length=120)
    uf = models.CharField(max_length=2)
    responsavel = models.CharField(max_length=255, blank=True)
    membros = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, default='ATIVA')
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='children',
    )

    class Meta:
        ordering = ['nome']
        indexes = [
            models.Index(fields=['parent']),
            models.Index(fields=['tipo']),
            models.Index(fields=['formato']),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.tipo == TIPO_CAMPO:
            if self.parent_id:
                raise ValidationError({'parent': 'Campo não pode ter organização pai.'})
            if self.formato and self.formato != FORMATO_CAMPO:
                raise ValidationError({'formato': 'Campo deve usar formato CAMPO.'})
            self.formato = FORMATO_CAMPO
            return

        if self.tipo == TIPO_IGREJA:
            if self.parent_id:
                if self.parent.tipo != TIPO_CAMPO:
                    raise ValidationError({'parent': 'Igreja deve pertencer a um campo.'})
                self.formato = ''
                return
            self.formato = self.formato or FORMATO_IGREJA_INDIVIDUAL
            if self.formato != FORMATO_IGREJA_INDIVIDUAL:
                raise ValidationError({'formato': 'Igreja sem campo deve ser contrato individual.'})
            return

        raise ValidationError({'tipo': 'Tipo de organização inválido.'})

    def save(self, *args, **kwargs):
        if self.tipo == TIPO_CAMPO:
            self.formato = FORMATO_CAMPO
        elif self.tipo == TIPO_IGREJA and self.parent_id:
            self.formato = ''
        elif self.tipo == TIPO_IGREJA and not self.parent_id:
            self.formato = self.formato or FORMATO_IGREJA_INDIVIDUAL
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class OrganizationMembership(AuditModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organization_memberships')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    role_scope = models.CharField(max_length=100, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'organization')

    def __str__(self):
        return f'{self.user_id}::{self.organization_id}'
