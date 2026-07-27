from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from organizations.models import Organization

from .context import get_activity_request, mark_entity_event
from .services import record_activity


TRACKED_APPS = {
    'accounts',
    'organizations',
    'access_control',
    'classrooms',
    'students',
    'lessons',
    'attendance',
    'finance',
    'publications',
    'notifications',
}

EXCLUDED_MODELS = {
    'students.studenthistory',
}

SENSITIVE_FIELDS = {
    'password',
    'token',
    'access_token',
    'refresh_token',
}

IGNORED_FIELDS = {
    'created_at',
    'updated_at',
    'last_login',
}

MODEL_LABELS = {
    'accounts.user': ('usuário', 'Usuários'),
    'organizations.organization': ('organização', 'Organizações'),
    'organizations.organizationmembership': ('vínculo de organização', 'Usuários'),
    'access_control.role': ('perfil de acesso', 'Permissões'),
    'access_control.modulepermission': ('permissão de módulo', 'Permissões'),
    'access_control.rolepermission': ('permissão de perfil', 'Permissões'),
    'access_control.userrole': ('perfil de usuário', 'Usuários'),
    'classrooms.classgroup': ('turma', 'Turmas'),
    'classrooms.classteacher': ('vínculo de professor', 'Turmas'),
    'students.student': ('aluno', 'Alunos'),
    'students.studentaddress': ('endereço de aluno', 'Alunos'),
    'students.studentguardian': ('responsável de aluno', 'Alunos'),
    'students.studentimportbatch': ('importação de alunos', 'Alunos'),
    'students.studentimportrow': ('linha de importação', 'Alunos'),
    'lessons.trimester': ('trimestre', 'Lições'),
    'lessons.lesson': ('lição', 'Lições'),
    'lessons.lessonschedule': ('escala de aula', 'Lições'),
    'attendance.attendancesheet': ('registro de frequência', 'Frequência'),
    'attendance.attendancerecord': ('presença de aluno', 'Frequência'),
    'finance.offering': ('oferta', 'Financeiro'),
    'publications.publicationcontrol': ('controle de revista', 'Revistas'),
    'notifications.notification': ('notificação', 'Notificações'),
}

RELATION_PATHS = (
    ('class_group',),
    ('student',),
    ('attendance_sheet', 'class_group'),
    ('batch',),
    ('lesson',),
    ('trimester',),
)


def _is_tracked(sender):
    label = sender._meta.label_lower
    return (
        sender._meta.app_label in TRACKED_APPS
        and label not in EXCLUDED_MODELS
    )


def _json_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if hasattr(value, 'name'):
        return str(value.name)
    return str(value)


def _snapshot(instance):
    data = {}
    for field in instance._meta.concrete_fields:
        field_name = field.name
        if field.primary_key or field_name in IGNORED_FIELDS:
            continue
        if field_name in SENSITIVE_FIELDS or 'password' in field_name.lower():
            continue
        data[field.attname] = _json_value(getattr(instance, field.attname, None))
    return data


def _changes(before, after, created=False):
    if created:
        return {
            field: {'antes': None, 'depois': value}
            for field, value in after.items()
            if value not in (None, '')
        }
    return {
        field: {'antes': before.get(field), 'depois': value}
        for field, value in after.items()
        if before.get(field) != value
    }


def _request_organization_id(request):
    user = getattr(request, 'user', None)
    raw_id = request.META.get('HTTP_X_ORGANIZATION_ID')
    return raw_id or getattr(user, 'active_organization_id', None)


def _related_organization_id(instance):
    direct_id = getattr(instance, 'organization_id', None)
    if direct_id:
        return direct_id

    for path in RELATION_PATHS:
        current = instance
        try:
            for part in path:
                current = getattr(current, part)
        except (AttributeError, ObjectDoesNotExist):
            continue
        related_id = getattr(current, 'organization_id', None)
        if related_id:
            return related_id
    return None


def _organization_id(instance, request):
    if instance._meta.label_lower == 'organizations.organization':
        return instance.pk
    return _related_organization_id(instance) or _request_organization_id(request)


def _reference(instance):
    pk = getattr(instance, 'pk', None)
    text = str(instance)
    default_text = f'{instance.__class__.__name__} object ({pk})'
    if text and text != default_text:
        return f'ID {pk} · {text}'[:120]
    return f'ID {pk}'[:120]


def _record_entity_event(instance, *, event_type, changes, organization_id=None):
    request = get_activity_request()
    user = getattr(request, 'user', None) if request else None
    if not request or not user or not user.is_authenticated:
        return

    organization_id = organization_id or _organization_id(instance, request)
    try:
        organization = Organization.objects.filter(id=organization_id).first()
    except (TypeError, ValueError):
        organization = None
    if organization is None:
        return

    label = instance._meta.label_lower
    singular, resource = MODEL_LABELS.get(
        label,
        (instance._meta.verbose_name, instance._meta.verbose_name_plural.title()),
    )
    verb = {
        'CREATE': 'Criou',
        'UPDATE': 'Editou',
        'DELETE': 'Excluiu',
    }[event_type]
    record_activity(
        request=request,
        user=user,
        organization=organization,
        action=f'{verb} {singular}',
        resource=resource,
        object_reference=_reference(instance),
        event_type=event_type,
        model_label=label,
        changes=changes,
        status_code=200,
    )
    mark_entity_event()


@receiver(pre_save)
def activity_pre_save(sender, instance, **kwargs):
    if not _is_tracked(sender) or not instance.pk:
        return
    try:
        previous = sender._default_manager.get(pk=instance.pk)
    except sender.DoesNotExist:
        previous = None
    instance._activity_log_before = _snapshot(previous) if previous else {}


@receiver(post_save)
def activity_post_save(sender, instance, created, **kwargs):
    if not _is_tracked(sender):
        return
    before = getattr(instance, '_activity_log_before', {})
    after = _snapshot(instance)
    changed = _changes(before, after, created=created)
    if not created and not changed:
        return
    request = get_activity_request()
    became_inactive = any(
        field in changed
        and changed[field]['antes'] is True
        and changed[field]['depois'] is False
        for field in ('is_active', 'ativo')
    )
    event_type = 'CREATE' if created else 'UPDATE'
    if not created and (
        became_inactive or (request and request.method == 'DELETE')
    ):
        event_type = 'DELETE'
    _record_entity_event(
        instance,
        event_type=event_type,
        changes=changed,
    )


@receiver(pre_delete)
def activity_pre_delete(sender, instance, **kwargs):
    if not _is_tracked(sender):
        return
    request = get_activity_request()
    instance._activity_log_before = _snapshot(instance)
    instance._activity_log_organization_id = (
        _organization_id(instance, request) if request else None
    )


@receiver(post_delete)
def activity_post_delete(sender, instance, **kwargs):
    if not _is_tracked(sender):
        return
    before = getattr(instance, '_activity_log_before', _snapshot(instance))
    changed = {
        field: {'antes': value, 'depois': None}
        for field, value in before.items()
        if value not in (None, '')
    }
    _record_entity_event(
        instance,
        event_type='DELETE',
        changes=changed,
        organization_id=getattr(instance, '_activity_log_organization_id', None),
    )
