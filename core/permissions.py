from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission

from core.scoping import get_roles_for_active_org, is_admin_sistema
from core.tenant import resolve_active_organization


class IsAdminSistema(BasePermission):
    message = 'Apenas administradores do sistema podem realizar esta operação.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and is_admin_sistema(user))


class HasModulePermission(BasePermission):
    module = None
    action = None
    require_organization = True

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if not self.module or not self.action:
            return True

        # Admin do sistema tem acesso a tudo, mesmo sem contexto ativo (ex.: criar o
        # primeiro usuário/organização numa instalação nova). Checado antes de exigir
        # organização, pois resolve_active_organization(required=True) lança sem contexto.
        if is_admin_sistema(user):
            return True

        try:
            org = resolve_active_organization(request, required=self.require_organization)
        except ValidationError:
            return False

        if org is None:
            return False

        for user_role in get_roles_for_active_org(user, org):
            for role_permission in user_role.role.permissions.select_related('permission').all():
                perm = role_permission.permission
                if perm.modulo != self.module:
                    continue
                if getattr(perm, self.action, False):
                    return True
        return False


def module_permission(module, action, require_organization=True):
    class _ModulePermission(HasModulePermission):
        pass

    _ModulePermission.module = module
    _ModulePermission.action = action
    _ModulePermission.require_organization = require_organization
    return _ModulePermission
