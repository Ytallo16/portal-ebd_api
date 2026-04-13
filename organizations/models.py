from django.conf import settings
from django.db import models

from core.models import AuditModel, SoftDeleteModel


class Organization(AuditModel, SoftDeleteModel):
    TIPO_CHOICES = [
        ('SEDE', 'Sede'),
        ('FILIAL', 'Filial'),
        ('CONGREGACAO', 'Congregação'),
    ]

    nome = models.CharField(max_length=255)
    sigla = models.CharField(max_length=50)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    cidade = models.CharField(max_length=120)
    uf = models.CharField(max_length=2)
    responsavel = models.CharField(max_length=255, blank=True)
    membros = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, default='ATIVA')

    class Meta:
        ordering = ['nome']

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
