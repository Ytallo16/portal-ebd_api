from rest_framework.permissions import BasePermission


class HasModulePermission(BasePermission):
    module = None
    action = None

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if not self.module or not self.action:
            return True

        roles = user.user_roles.select_related('role').prefetch_related('role__permissions__permission')
        for user_role in roles:
            permissions = user_role.role.permissions.all()
            for role_permission in permissions:
                perm = role_permission.permission
                if perm.modulo != self.module:
                    continue
                if getattr(perm, self.action, False):
                    return True
        return False


def module_permission(module, action):
    class _ModulePermission(HasModulePermission):
        pass

    _ModulePermission.module = module
    _ModulePermission.action = action
    return _ModulePermission
