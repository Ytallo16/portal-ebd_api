from django.conf import settings
from django.db import models

from core.models import AuditModel


class Role(AuditModel):
    nome = models.CharField(max_length=120, unique=True)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome


class ModulePermission(AuditModel):
    modulo = models.CharField(max_length=100)
    visualizar = models.BooleanField(default=False)
    criar = models.BooleanField(default=False)
    editar = models.BooleanField(default=False)
    excluir = models.BooleanField(default=False)
    aprovar = models.BooleanField(default=False)

    class Meta:
        unique_together = ('modulo',)
        ordering = ['modulo']

    def __str__(self):
        return self.modulo


class RolePermission(AuditModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permissions')
    permission = models.ForeignKey(ModulePermission, on_delete=models.CASCADE, related_name='roles')

    class Meta:
        unique_together = ('role', 'permission')


class UserRole(AuditModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE, null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'role', 'organization')
