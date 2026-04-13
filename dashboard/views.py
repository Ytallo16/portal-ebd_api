from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from attendance.models import AttendanceRecord
from classrooms.models import ClassGroup
from core.tenant import get_user_organization
from finance.models import Offering
from students.models import Student


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def summary(request):
    org = get_user_organization(request)
    total_students = Student.objects.filter(organization=org, is_active=True).count()
    total_classes = ClassGroup.objects.filter(organization=org, is_active=True).count()
    total_offerings = Offering.objects.filter(organization=org, is_active=True).aggregate(total=Sum('valor'))['total'] or 0
    presentes = AttendanceRecord.objects.filter(attendance_sheet__lesson__organization=org, presente=True).count()
    ausentes = AttendanceRecord.objects.filter(attendance_sheet__lesson__organization=org, presente=False).count()

    return Response(
        {
            'total_students': total_students,
            'total_classes': total_classes,
            'total_offerings': total_offerings,
            'attendance': {'presentes': presentes, 'ausentes': ausentes},
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attendance_evolution(request):
    org = get_user_organization(request)
    rows = (
        AttendanceRecord.objects.filter(attendance_sheet__lesson__organization=org)
        .values('attendance_sheet__lesson__data')
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
@permission_classes([IsAuthenticated])
def offering_evolution(request):
    org = get_user_organization(request)
    rows = Offering.objects.filter(organization=org, is_active=True).values('data').annotate(total=Sum('valor')).order_by('data')
    return Response(list(rows))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def class_composition(request):
    org = get_user_organization(request)
    rows = (
        ClassGroup.objects.filter(organization=org, is_active=True)
        .annotate(total=Count('students', filter=Q(students__is_active=True)))
        .values('id', 'nome', 'cor', 'total')
        .order_by('nome')
    )
    return Response(list(rows))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def birthdays(request):
    org = get_user_organization(request)
    today = date.today()
    future = today + timedelta(days=30)

    students = Student.objects.filter(organization=org, is_active=True).select_related('class_group')
    payload = []
    for student in students:
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
