from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from attendance.models import AttendanceRecord, AttendanceSheet
from classrooms.models import ClassGroup
from core.permissions import module_permission
from core.scoping import get_teaching_class_ids, user_is_professor
from core.tenant import get_operational_organization, resolve_active_organization
from core.viewmixins import DashboardOrganizationMixin
from finance.models import Offering
from students.models import Student

from .services import build_professor_dashboard


class DashboardRequestMixin(DashboardOrganizationMixin):
    request = None

    def __init__(self, request):
        self.request = request


def _org_ids(request):
    mixin = DashboardRequestMixin(request)
    return mixin.get_dashboard_organization_ids()


def _class_ids_for_dashboard(request):
    try:
        active_org = resolve_active_organization(request, required=False)
    except Exception:
        return None

    if active_org and user_is_professor(request.user, active_org):
        return get_teaching_class_ids(request.user, active_org)
    return None


def _student_queryset(request):
    org_ids = _org_ids(request)
    queryset = Student.objects.filter(organization_id__in=org_ids, is_active=True)
    class_ids = _class_ids_for_dashboard(request)
    if class_ids is not None:
        queryset = queryset.filter(class_group_id__in=class_ids)
    return queryset


@api_view(['GET'])
@permission_classes([IsAuthenticated, module_permission('dashboard', 'visualizar')])
def summary(request):
    org_ids = _org_ids(request)
    class_ids = _class_ids_for_dashboard(request)

    students = Student.objects.filter(organization_id__in=org_ids, is_active=True)
    classes = ClassGroup.objects.filter(organization_id__in=org_ids, is_active=True)
    offerings = Offering.objects.filter(organization_id__in=org_ids, is_active=True)
    attendance = AttendanceRecord.objects.filter(attendance_sheet__lesson__organization_id__in=org_ids)
    sheets = AttendanceSheet.objects.filter(lesson__organization_id__in=org_ids)

    if class_ids is not None:
        students = students.filter(class_group_id__in=class_ids)
        classes = classes.filter(id__in=class_ids)
        offerings = offerings.filter(class_group_id__in=class_ids)
        attendance = attendance.filter(attendance_sheet__class_group_id__in=class_ids)
        sheets = sheets.filter(class_group_id__in=class_ids)

    presentes = attendance.filter(presente=True).count()
    ausentes = attendance.filter(presente=False).count()
    visitantes = sheets.aggregate(total=Sum('visitantes'))['total'] or 0

    return Response(
        {
            'total_students': students.count(),
            'total_classes': classes.count(),
            'total_offerings': offerings.aggregate(total=Sum('valor'))['total'] or 0,
            'total_visitors': visitantes,
            'attendance': {'presentes': presentes, 'ausentes': ausentes},
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, module_permission('dashboard', 'visualizar')])
def attendance_evolution(request):
    org_ids = _org_ids(request)
    class_ids = _class_ids_for_dashboard(request)

    queryset = AttendanceRecord.objects.filter(attendance_sheet__lesson__organization_id__in=org_ids)
    if class_ids is not None:
        queryset = queryset.filter(attendance_sheet__class_group_id__in=class_ids)

    rows = (
        queryset.values('attendance_sheet__lesson__data')
        .annotate(
            presentes=Count('id', filter=Q(presente=True)),
            ausentes=Count('id', filter=Q(presente=False)),
        )
        .order_by('attendance_sheet__lesson__data')
    )
    return Response(
        [
            {
                'data': row['attendance_sheet__lesson__data'],
                'presentes': row['presentes'],
                'ausentes': row['ausentes'],
            }
            for row in rows
        ]
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, module_permission('dashboard', 'visualizar')])
def offering_evolution(request):
    org_ids = _org_ids(request)
    class_ids = _class_ids_for_dashboard(request)

    queryset = Offering.objects.filter(organization_id__in=org_ids, is_active=True)
    if class_ids is not None:
        queryset = queryset.filter(class_group_id__in=class_ids)

    rows = queryset.values('data').annotate(total=Sum('valor')).order_by('data')
    return Response(list(rows))


@api_view(['GET'])
@permission_classes([IsAuthenticated, module_permission('dashboard', 'visualizar')])
def class_composition(request):
    org_ids = _org_ids(request)
    class_ids = _class_ids_for_dashboard(request)

    queryset = ClassGroup.objects.filter(organization_id__in=org_ids, is_active=True)
    if class_ids is not None:
        queryset = queryset.filter(id__in=class_ids)

    rows = (
        queryset.annotate(total=Count('students', filter=Q(students__is_active=True)))
        .values('id', 'nome', 'cor', 'total')
        .order_by('nome')
    )
    return Response(list(rows))


@api_view(['GET'])
@permission_classes([IsAuthenticated, module_permission('dashboard', 'visualizar')])
def birthdays(request):
    students = _student_queryset(request)
    today = date.today()
    future = today + timedelta(days=30)

    payload = []
    for student in students.select_related('class_group'):
        current_year_birthday = student.data_nascimento.replace(year=today.year)
        if current_year_birthday < today:
            current_year_birthday = current_year_birthday.replace(year=today.year + 1)
        if today <= current_year_birthday <= future:
            payload.append(
                {
                    'nome': student.nome,
                    'data': current_year_birthday,
                    'turma': student.class_group.nome if student.class_group else None,
                    'dias_para_aniversario': (current_year_birthday - today).days,
                }
            )

    payload.sort(key=lambda x: x['dias_para_aniversario'])
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated, module_permission('dashboard', 'visualizar')])
def professor_dashboard(request):
    org = get_operational_organization(request)
    class_id = request.query_params.get('class_id')
    payload = build_professor_dashboard(request.user, org, class_id=class_id)
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated, module_permission('dashboard', 'visualizar')])
def professor_ranking(request):
    org_ids = _org_ids(request)
    class_ids = _class_ids_for_dashboard(request)
    try:
        trimestre = int(request.query_params.get('trimestre') or '')
        ano = int(request.query_params.get('ano') or '')
    except (TypeError, ValueError):
        return Response({'detail': 'Informe ano e trimestre válidos.'}, status=400)

    if trimestre < 1 or trimestre > 4:
        return Response({'detail': 'Trimestre inválido.'}, status=400)

    class_id_param = request.query_params.get('class_id')
    if class_id_param is not None:
        try:
            class_id_param = int(class_id_param)
        except (TypeError, ValueError):
            return Response({'detail': 'class_id inválido.'}, status=400)

    sheets = AttendanceSheet.objects.filter(
        lesson__organization_id__in=org_ids,
        lesson__trimestre=trimestre,
        lesson__ano=ano,
        professor__isnull=False,
        class_group__is_active=True,
    )
    if class_ids is not None:
        sheets = sheets.filter(class_group_id__in=class_ids)
    if class_id_param is not None:
        sheets = sheets.filter(class_group_id=class_id_param)

    rows = (
        sheets.values('professor_id', 'professor__nome')
        .annotate(
            presencas=Count('id', filter=Q(professor_presente=True)),
            ausencias=Count('id', filter=Q(professor_presente=False)),
            turma_ids=Count('class_group', distinct=True),
        )
        .order_by()
    )

    turma_rows = (
        sheets.values('professor_id', 'class_group_id', 'class_group__nome')
        .distinct()
        .order_by('class_group__nome')
    )
    turma_map = {}
    for row in turma_rows:
        professor_id = row['professor_id']
        turma_map.setdefault(professor_id, {'ids': [], 'nomes': []})
        turma_map[professor_id]['ids'].append(str(row['class_group_id']))
        turma_map[professor_id]['nomes'].append(row['class_group__nome'])

    payload = []
    for row in rows:
        total = row['presencas'] + row['ausencias']
        turma_info = turma_map.get(row['professor_id'], {'ids': [], 'nomes': []})
        payload.append(
            {
                'professorId': row['professor_id'],
                'professorNome': row['professor__nome'] or f"Professor #{row['professor_id']}",
                'turmaIds': turma_info['ids'],
                'turmaNomes': turma_info['nomes'],
                'presencas': row['presencas'],
                'ausencias': row['ausencias'],
                'totalRegistros': total,
                'presencaPct': (row['presencas'] / total) * 100 if total else 0,
            }
        )

    payload.sort(key=lambda item: (-item['presencaPct'], -item['presencas']))
    return Response(payload)
