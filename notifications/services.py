from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.utils import timezone

from access_control.constants import FULL_OPERATIONAL_ROLES
from attendance.models import AttendanceSheet
from classrooms.models import ClassGroup
from core.scoping import get_roles_for_active_org, get_teaching_class_ids, is_admin_sistema
from dashboard.services import _build_aniversariantes, _trimestre_referencia
from lessons.models import Lesson, LessonSchedule
from publications.models import PublicationControl

from .constants import (
    KIND_ATTENDANCE_PENDING,
    KIND_BIRTHDAY_TODAY,
    KIND_LESSON_FINALIZE,
    KIND_LESSON_TODAY,
    KIND_MAGAZINE_PAYMENT,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)
from .models import Notification

MAX_ATTENDANCE_NOTIFICATIONS = 8


@dataclass
class DesiredNotification:
    dedupe_key: str
    kind: str
    title: str
    body: str
    action_path: str
    severity: str
    metadata: dict


def _licao_turma_path(lesson, class_id):
    return f'/licoes/{lesson.ano}/{lesson.trimestre}/{lesson.numero}/turmas/{class_id}'


def _licao_path(lesson):
    return f'/licoes/{lesson.ano}/{lesson.trimestre}/{lesson.numero}'


def _user_has_operational_role(user, org):
    if is_admin_sistema(user):
        return True
    role_names = {user_role.role.nome for user_role in get_roles_for_active_org(user, org)}
    return bool(role_names.intersection(FULL_OPERATIONAL_ROLES))


def _collect_professor_desired(user, org):
    class_ids = get_teaching_class_ids(user, org)
    if not class_ids:
        return []

    trimestre = _trimestre_referencia(org)
    if not trimestre:
        return []

    today = date.today()
    desired = []
    attendance_count = 0

    lessons = list(
        Lesson.objects.filter(
            organization=org,
            trimestre=trimestre.numero,
            ano=trimestre.ano,
            is_active=True,
        ).order_by('data', 'numero')
    )
    lesson_ids = [lesson.id for lesson in lessons]

    for class_id in class_ids:
        turma = ClassGroup.objects.filter(id=class_id, organization=org, is_active=True).first()
        if not turma:
            continue

        sheet_lesson_ids = set(
            AttendanceSheet.objects.filter(
                class_group_id=class_id,
                lesson_id__in=lesson_ids,
            ).values_list('lesson_id', flat=True)
        )

        pending_lessons = [lesson for lesson in lessons if lesson.id not in sheet_lesson_ids]
        for lesson in pending_lessons[:MAX_ATTENDANCE_NOTIFICATIONS]:
            if attendance_count >= MAX_ATTENDANCE_NOTIFICATIONS:
                break
            desired.append(
                DesiredNotification(
                    dedupe_key=f'attendance:lesson:{lesson.id}:class:{class_id}',
                    kind=KIND_ATTENDANCE_PENDING,
                    title=f'Chamada pendente — {turma.nome}',
                    body=f'Lição {lesson.numero}: {lesson.tema} ainda não foi registrada.',
                    action_path=_licao_turma_path(lesson, class_id),
                    severity=SEVERITY_WARNING,
                    metadata={
                        'lesson_id': lesson.id,
                        'lesson_numero': lesson.numero,
                        'class_id': class_id,
                        'turma_nome': turma.nome,
                    },
                )
            )
            attendance_count += 1

        schedules_today = LessonSchedule.objects.filter(
            class_group_id=class_id,
            professor=user,
            lesson__in=lessons,
            lesson__data=today,
        ).select_related('lesson', 'class_group')

        for schedule in schedules_today:
            lesson = schedule.lesson
            if lesson.id in sheet_lesson_ids:
                continue
            desired.append(
                DesiredNotification(
                    dedupe_key=f'lesson_today:lesson:{lesson.id}:class:{class_id}',
                    kind=KIND_LESSON_TODAY,
                    title=f'Aula hoje — {turma.nome}',
                    body=f'Lição {lesson.numero}: {lesson.tema}. Registre a chamada da EBD.',
                    action_path=_licao_turma_path(lesson, class_id),
                    severity=SEVERITY_WARNING,
                    metadata={
                        'lesson_id': lesson.id,
                        'lesson_numero': lesson.numero,
                        'class_id': class_id,
                    },
                )
            )

        students_qs = turma.students.filter(organization=org, is_active=True)
        birthdays = _build_aniversariantes(students_qs, today=today, horizon_days=0)
        if birthdays:
            nomes = ', '.join(item['nome'] for item in birthdays[:3])
            extra = len(birthdays) - 3
            if extra > 0:
                nomes = f'{nomes} e mais {extra}'
            desired.append(
                DesiredNotification(
                    dedupe_key=f'birthday_today:class:{class_id}',
                    kind=KIND_BIRTHDAY_TODAY,
                    title='Aniversário hoje',
                    body=f'{nomes} — turma {turma.nome}.',
                    action_path='/',
                    severity=SEVERITY_INFO,
                    metadata={'class_id': class_id, 'count': len(birthdays)},
                )
            )

    return desired


def _collect_secretary_desired(user, org):
    if not _user_has_operational_role(user, org):
        return []

    today = date.today()
    desired = []
    trimestre = _trimestre_referencia(org)

    active_classes = ClassGroup.objects.filter(
        organization=org,
        ativa=True,
        is_active=True,
    )

    lessons_to_finalize = Lesson.objects.filter(
        organization=org,
        status='ABERTA',
        data__lte=today,
        is_active=True,
    ).order_by('data', 'numero')

    for lesson in lessons_to_finalize[:10]:
        pending_turmas = []
        for class_group in active_classes:
            if not AttendanceSheet.objects.filter(lesson=lesson, class_group=class_group).exists():
                pending_turmas.append(class_group.nome)
        if pending_turmas:
            turmas_txt = ', '.join(pending_turmas[:3])
            if len(pending_turmas) > 3:
                turmas_txt = f'{turmas_txt} e mais {len(pending_turmas) - 3}'
            desired.append(
                DesiredNotification(
                    dedupe_key=f'lesson_finalize:lesson:{lesson.id}',
                    kind=KIND_LESSON_FINALIZE,
                    title=f'Lição {lesson.numero} aguardando encerramento',
                    body=(
                        f'{lesson.tema} — registre ou finalize após concluir as turmas: {turmas_txt}.'
                    ),
                    action_path=_licao_path(lesson),
                    severity=SEVERITY_WARNING,
                    metadata={
                        'lesson_id': lesson.id,
                        'lesson_numero': lesson.numero,
                        'turmas_pendentes': pending_turmas,
                    },
                )
            )

    if trimestre:
        pending_payment = PublicationControl.objects.filter(
            organization=org,
            trimester=trimestre,
            is_active=True,
            recebeu=True,
            pagou=False,
        ).count()
        if pending_payment > 0:
            desired.append(
                DesiredNotification(
                    dedupe_key=f'magazine_payment:trimester:{trimestre.id}',
                    kind=KIND_MAGAZINE_PAYMENT,
                    title='Revistas aguardando pagamento',
                    body=(
                        f'{pending_payment} pessoa(s) receberam a revista e ainda não constam como pagas.'
                    ),
                    action_path='/revistas',
                    severity=SEVERITY_WARNING,
                    metadata={'count': pending_payment, 'trimester_id': trimestre.id},
                )
            )

    from students.models import Student

    students_qs = Student.objects.filter(organization=org, is_active=True)
    birthdays = _build_aniversariantes(students_qs, today=today, horizon_days=0)
    if birthdays:
        nomes = ', '.join(item['nome'] for item in birthdays[:3])
        extra = len(birthdays) - 3
        if extra > 0:
            nomes = f'{nomes} e mais {extra}'
        desired.append(
            DesiredNotification(
                dedupe_key=f'birthday_today:org:{org.id}',
                kind=KIND_BIRTHDAY_TODAY,
                title='Aniversariantes hoje',
                body=f'{len(birthdays)} aniversário(s): {nomes}.',
                action_path='/',
                severity=SEVERITY_INFO,
                metadata={'count': len(birthdays)},
            )
        )

    return desired


def collect_desired_notifications(user, org):
    desired = []
    class_ids = get_teaching_class_ids(user, org)
    if class_ids:
        desired.extend(_collect_professor_desired(user, org))
    if _user_has_operational_role(user, org):
        desired.extend(_collect_secretary_desired(user, org))

    by_key = {}
    for item in desired:
        by_key[item.dedupe_key] = item
    return list(by_key.values())


@transaction.atomic
def sync_user_notifications(user, org):
    desired = collect_desired_notifications(user, org)
    desired_keys = {item.dedupe_key for item in desired}

    for item in desired:
        notification, created = Notification.objects.get_or_create(
            user=user,
            organization=org,
            dedupe_key=item.dedupe_key,
            defaults={
                'kind': item.kind,
                'title': item.title,
                'body': item.body,
                'action_path': item.action_path,
                'severity': item.severity,
                'metadata': item.metadata,
            },
        )
        if not created:
            notification.kind = item.kind
            notification.title = item.title
            notification.body = item.body
            notification.action_path = item.action_path
            notification.severity = item.severity
            notification.metadata = item.metadata
            notification.save(
                update_fields=[
                    'kind',
                    'title',
                    'body',
                    'action_path',
                    'severity',
                    'metadata',
                    'updated_at',
                ]
            )

    Notification.objects.filter(user=user, organization=org).exclude(
        dedupe_key__in=desired_keys
    ).delete()

    return desired_keys


def mark_notification_read(notification):
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at', 'updated_at'])


def mark_all_notifications_read(user, org):
    now = timezone.now()
    return Notification.objects.filter(
        user=user,
        organization=org,
        read_at__isnull=True,
    ).update(read_at=now, updated_at=now)
