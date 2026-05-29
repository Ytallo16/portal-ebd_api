from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission

from core.scoping import get_roles_for_active_org, is_admin_sistema
from core.tenant import resolve_active_organization


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

        try:
            org = resolve_active_organization(request, required=self.require_organization)
        except ValidationError:
            return False

        if is_admin_sistema(user):
            return True

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
