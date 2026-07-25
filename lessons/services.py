from datetime import date

from access_control.constants import ROLE_PROFESSOR, SECRETARY_ROLES
from core.scoping import get_role_names_for_organization, is_admin_sistema


def can_manage_lessons(user, organization):
    if is_admin_sistema(user):
        return True

    role_names = get_role_names_for_organization(user, organization)
    return bool(role_names.intersection(SECRETARY_ROLES))


def can_manage_trimesters(user, organization):
    return can_manage_lessons(user, organization)


def can_edit_lesson(user, lesson):
    if is_admin_sistema(user):
        return True

    role_names = get_role_names_for_organization(
        user,
        getattr(lesson, 'organization', None),
    )
    if role_names.intersection(SECRETARY_ROLES):
        return True

    if ROLE_PROFESSOR in role_names:
        return lesson.data == date.today()

    return False


def can_edit_class_lesson_registration(user, class_group, lesson):
    """Presenças, totais (bíblias, revistas, ofertas, visitantes) na ficha da turma."""
    if is_admin_sistema(user):
        return True

    role_names = get_role_names_for_organization(user, class_group.organization)
    if role_names.intersection(SECRETARY_ROLES):
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
    return can_edit_class_lesson_registration(
        user,
        sheet.class_group,
        sheet.lesson,
    )
