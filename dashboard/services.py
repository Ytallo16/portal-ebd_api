from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from attendance.models import AttendanceRecord, AttendanceSheet
from classrooms.models import ClassGroup
from core.scoping import get_teaching_class_ids, user_is_professor
from lessons.models import Lesson, LessonSchedule, Trimester
from students.models import Student


def _pct(presentes, ausentes):
    total = presentes + ausentes
    if total == 0:
        return 0
    return round((presentes / total) * 100)


def _trimestre_referencia(org):
    trimestre = (
        Trimester.objects.filter(organization=org, is_active=True, status='EM_ANDAMENTO')
        .order_by('-ano', '-numero')
        .first()
    )
    if trimestre:
        return trimestre

    lesson = (
        Lesson.objects.filter(organization=org, is_active=True)
        .order_by('-ano', '-trimestre')
        .first()
    )
    if not lesson:
        return None

    return Trimester.objects.filter(
        organization=org,
        ano=lesson.ano,
        numero=lesson.trimestre,
        is_active=True,
    ).first()


def _find_proxima_licao(lessons, sheet_lesson_ids):
    if not lessons:
        return None

    today = date.today()
    ranked = sorted(
        lessons,
        key=lambda lesson: abs((lesson.data - today).days),
    )
    lesson = ranked[0]
    return {
        'id': lesson.id,
        'numero': lesson.numero,
        'tema': lesson.tema,
        'data': lesson.data,
        'revista': lesson.revista,
        'texto_aureo': lesson.texto_aureo,
        'registrada': lesson.id in sheet_lesson_ids,
    }


def _build_aniversariantes(students_qs, today=None, horizon_days=30):
    today = today or date.today()
    future = today + timedelta(days=horizon_days)
    payload = []

    for student in students_qs:
        current_year_birthday = student.data_nascimento.replace(year=today.year)
        if current_year_birthday < today:
            current_year_birthday = current_year_birthday.replace(year=today.year + 1)
        if today <= current_year_birthday <= future:
            payload.append(
                {
                    'nome': student.nome,
                    'data': current_year_birthday,
                    'dias_para_aniversario': (current_year_birthday - today).days,
                }
            )

    payload.sort(key=lambda item: item['dias_para_aniversario'])
    return payload


def _build_ranking_alunos(records_qs):
    rows = records_qs.values('student_id', 'student__nome').annotate(
        presencas=Count('id', filter=Q(presente=True)),
        ausencias=Count('id', filter=Q(presente=False)),
    )
    return [
        {
            'id': row['student_id'],
            'nome': row['student__nome'],
            'presencas': row['presencas'],
            'ausencias': row['ausencias'],
        }
        for row in rows
        if row['presencas'] > 0 or row['ausencias'] > 0
    ]


def _build_evolucao_frequencia(sheets, limit=12):
    ordered = sorted(sheets, key=lambda sheet: sheet.lesson.data)[-limit:]
    payload = []
    for sheet in ordered:
        presentes = sheet.records.filter(presente=True).count()
        ausentes = sheet.records.filter(presente=False).count()
        payload.append(
            {
                'data': sheet.lesson.data,
                'licao_numero': sheet.lesson.numero,
                'presentes': presentes,
                'ausentes': ausentes,
                'pct': _pct(presentes, ausentes),
            }
        )
    return payload


def require_professor_classes(user, org):
    if not user_is_professor(user, org):
        raise PermissionDenied('Apenas professores podem acessar este painel.')

    class_ids = get_teaching_class_ids(user, org)
    if not class_ids:
        raise NotFound('Nenhuma turma vinculada a este professor.')

    return class_ids


def resolve_class_group(org, class_ids, class_id=None):
    turmas = ClassGroup.objects.filter(
        organization=org,
        id__in=class_ids,
        is_active=True,
    ).order_by('nome')

    turmas_disponiveis = [{'id': t.id, 'nome': t.nome, 'cor': t.cor} for t in turmas]

    if class_id is not None:
        try:
            class_id = int(class_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError({'class_id': 'Informe um identificador de turma válido.'}) from exc
        if class_id not in class_ids:
            raise PermissionDenied('Você não leciona nesta turma.')
        turma = turmas.filter(id=class_id).first()
    else:
        turma = turmas.first()

    if not turma:
        raise NotFound('Turma não encontrada.')

    return turma, turmas_disponiveis


def build_professor_dashboard(user, org, class_id=None):
    class_ids = require_professor_classes(user, org)
    turma, turmas_disponiveis = resolve_class_group(org, class_ids, class_id)
    trimestre = _trimestre_referencia(org)

    trimestre_payload = None
    lessons = Lesson.objects.none()
    sheets = AttendanceSheet.objects.none()
    records = AttendanceRecord.objects.none()

    if trimestre:
        trimestre_payload = {
            'numero': trimestre.numero,
            'ano': trimestre.ano,
            'titulo': trimestre.titulo or f'{trimestre.numero}º Trimestre {trimestre.ano}',
        }
        lessons = Lesson.objects.filter(
            organization=org,
            trimestre=trimestre.numero,
            ano=trimestre.ano,
            is_active=True,
        ).order_by('data', 'numero')
        sheets = (
            AttendanceSheet.objects.filter(
                class_group=turma,
                lesson__in=lessons,
            )
            .select_related('lesson')
            .prefetch_related('records')
        )
        records = AttendanceRecord.objects.filter(attendance_sheet__in=sheets)

    sheet_lesson_ids = set(sheets.values_list('lesson_id', flat=True))
    lesson_ids = set(lessons.values_list('id', flat=True))
    pending_lessons = lessons.exclude(id__in=sheet_lesson_ids).order_by('data', 'numero')

    total_alunos = Student.objects.filter(
        organization=org,
        class_group=turma,
        is_active=True,
    ).count()

    presentes_total = records.filter(presente=True).count()
    ausentes_total = records.filter(presente=False).count()

    ofertas_trimestre = sheets.aggregate(total=Sum('oferta_valor'))['total'] or 0
    visitantes_trimestre = sheets.aggregate(total=Sum('visitantes'))['total'] or 0

    ultimo_sheet = sheets.order_by('-lesson__data', '-lesson__numero').first()
    ultimo_registro = None
    ultima_ebd_pct = None
    if ultimo_sheet:
        ult_presentes = ultimo_sheet.records.filter(presente=True).count()
        ult_ausentes = ultimo_sheet.records.filter(presente=False).count()
        ultima_ebd_pct = _pct(ult_presentes, ult_ausentes)
        ultimo_registro = {
            'licao_numero': ultimo_sheet.lesson.numero,
            'licao_tema': ultimo_sheet.lesson.tema,
            'data': ultimo_sheet.lesson.data,
            'presentes': ult_presentes,
            'ausentes': ult_ausentes,
            'visitantes': ultimo_sheet.visitantes,
            'biblias': ultimo_sheet.biblias,
            'revistas': ultimo_sheet.revistas,
            'oferta_valor': str(ultimo_sheet.oferta_valor),
        }

    proxima_licao = _find_proxima_licao(list(lessons), sheet_lesson_ids)

    scheduled_qs = (
        LessonSchedule.objects.filter(
            class_group=turma,
            professor=user,
            lesson__in=lessons,
        )
        .select_related('lesson')
        .order_by('lesson__data', 'lesson__numero')
    )
    sheets_by_lesson = {sheet.lesson_id: sheet for sheet in sheets}
    aulas_escaladas = []
    for schedule in scheduled_qs:
        sheet = sheets_by_lesson.get(schedule.lesson_id)
        presentes = sheet.records.filter(presente=True).count() if sheet else 0
        ausentes = sheet.records.filter(presente=False).count() if sheet else 0
        aulas_escaladas.append(
            {
                'id': schedule.lesson.id,
                'numero': schedule.lesson.numero,
                'tema': schedule.lesson.tema,
                'data': schedule.lesson.data,
                'registrada': sheet is not None,
                'presentes': presentes,
                'ausentes': ausentes,
            }
        )

    licoes_pendentes = [
        {
            'id': lesson.id,
            'numero': lesson.numero,
            'tema': lesson.tema,
            'data': lesson.data,
        }
        for lesson in pending_lessons[:5]
    ]

    students_qs = Student.objects.filter(
        organization=org,
        class_group=turma,
        is_active=True,
    )

    return {
        'turmas_disponiveis': turmas_disponiveis,
        'turma': {
            'id': turma.id,
            'nome': turma.nome,
            'cor': turma.cor,
            'total_alunos': total_alunos,
        },
        'trimestre': trimestre_payload,
        'resumo': {
            'frequencia_media_pct': _pct(presentes_total, ausentes_total),
            'pendencias_registro': len(lesson_ids - sheet_lesson_ids),
            'ultima_ebd_pct': ultima_ebd_pct,
            'ofertas_trimestre': str(ofertas_trimestre),
            'visitantes_trimestre': visitantes_trimestre or 0,
        },
        'proxima_licao': proxima_licao,
        'ultimo_registro': ultimo_registro,
        'aulas_escaladas': aulas_escaladas,
        'licoes_pendentes': licoes_pendentes,
        'evolucao_frequencia': _build_evolucao_frequencia(list(sheets)),
        'aniversariantes': _build_aniversariantes(students_qs),
        'ranking_alunos': _build_ranking_alunos(records),
    }
