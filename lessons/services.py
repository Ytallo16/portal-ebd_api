from datetime import date

from django.db.models import Q

from access_control.constants import ADMIN_ROLES, ROLE_PROFESSOR, SECRETARY_ROLES
from core.scoping import get_user_role_names


def can_manage_trimesters(user):
    if user.is_superuser:
        return True

    role_names = get_user_role_names(user)
    return bool(role_names.intersection(ADMIN_ROLES | SECRETARY_ROLES))


def can_edit_lesson(user, lesson):
    if user.is_superuser:
        return True

    role_names = get_user_role_names(user)
    if role_names.intersection(ADMIN_ROLES | SECRETARY_ROLES):
        return True

    if ROLE_PROFESSOR in role_names:
        return lesson.data == date.today()

    return False


def can_edit_class_lesson_registration(user, class_group, lesson):
    """Presenças, totais (bíblias, revistas, ofertas, visitantes) na ficha da turma."""
    if user.is_superuser:
        return True

    role_names = get_user_role_names(user)
    if role_names.intersection(ADMIN_ROLES | SECRETARY_ROLES):
        return True

    if ROLE_PROFESSOR in role_names:
        from core.scoping import get_teaching_class_ids

        class_ids = get_teaching_class_ids(user, class_group.organization)
        if class_group.id in class_ids:
            return True

        from .models import LessonSchedule

        return LessonSchedule.objects.filter(
            lesson=lesson,
            class_group=class_group,
            professor=user,
        ).exists()

    return False


def can_edit_attendance_sheet(user, sheet):
    if user.is_superuser:
        return True

    role_names = get_user_role_names(user)
    if role_names.intersection(ADMIN_ROLES | SECRETARY_ROLES):
        return True

    if ROLE_PROFESSOR in role_names:
        return can_edit_class_lesson_registration(
            user, sheet.class_group, sheet.lesson
        )

    return False
