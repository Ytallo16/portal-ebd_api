from django.core.management.base import BaseCommand
from django.db import transaction

from access_control.constants import ROLE_MODULE_MATRIX
from access_control.models import ModulePermission, Role, RolePermission


# Flags padrão de cada módulo (fonte única, alinhada ao seed_data).
MODULE_MATRIX = {
    'usuarios': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': True, 'aprovar': True},
    'organizacoes': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
    'turmas': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
    'alunos': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': True, 'aprovar': True},
    'licoes': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
    'frequencia': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
    'financeiro': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
    'revistas': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
    'dashboard': {'visualizar': True, 'criar': False, 'editar': False, 'excluir': False, 'aprovar': False},
}

ROLES_DATA = {
    'ADMINISTRADOR': 'Acesso total ao sistema',
    'SECRETARIO_CAMPO': 'Gestão completa do campo e igrejas filhas',
    'SECRETARIO_IGREJA': 'Gestão completa da igreja local',
    'PROFESSOR': 'Frequência, ofertas e acompanhamento da turma',
}


def _update_fields(instance, data):
    changed = False
    for field, value in data.items():
        if getattr(instance, field) != value:
            setattr(instance, field, value)
            changed = True
    if changed:
        instance.save()


class Command(BaseCommand):
    help = (
        'Cria/atualiza os papéis canônicos e as permissões de módulo (idempotente). '
        'Seguro para rodar em produção sem inserir dados de demonstração.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        permissions = {}
        for module, flags in MODULE_MATRIX.items():
            permission, _ = ModulePermission.objects.get_or_create(modulo=module, defaults=flags)
            _update_fields(permission, flags)
            permissions[module] = permission

        # Desativa papéis legados que possam existir.
        Role.objects.filter(nome__in=['ADMINISTRADOR_CAMPO', 'SECRETARIA', 'TESOUREIRO']).update(ativo=False)

        for role_name, descricao in ROLES_DATA.items():
            role, _ = Role.objects.get_or_create(
                nome=role_name,
                defaults={'descricao': descricao, 'ativo': True},
            )
            _update_fields(role, {'descricao': descricao, 'ativo': True})

            modules = ROLE_MODULE_MATRIX[role_name]
            for module in modules:
                RolePermission.objects.get_or_create(role=role, permission=permissions[module])
            RolePermission.objects.filter(role=role).exclude(
                permission__modulo__in=modules
            ).delete()

        self.stdout.write(self.style.SUCCESS('Papéis e permissões sincronizados.'))
