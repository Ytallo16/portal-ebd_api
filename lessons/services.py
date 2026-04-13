from datetime import date


def can_edit_lesson(user, lesson):
    if user.is_superuser:
        return True

    role_names = {
        user_role.role.nome.upper()
        for user_role in user.user_roles.select_related('role').filter(ativo=True)
    }

    admin_roles = {'ADMINISTRADOR', 'ADMIN_IGREJA', 'SECRETARIO_IGREJA', 'SECRETÁRIO DE IGREJA'}
    if role_names.intersection(admin_roles):
        return True

    professor_roles = {'PROFESSOR'}
    if role_names.intersection(professor_roles):
        return lesson.data == date.today()

    return False
