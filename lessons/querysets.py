from django.db.models import Count, Q


def with_attendance_totals(queryset):
    """Inclui totais de presença sem consultas adicionais durante a serialização."""
    return queryset.annotate(
        total_presentes=Count(
            'attendance_sheets__records',
            filter=Q(attendance_sheets__records__presente=True),
            distinct=True,
        ),
        total_ausentes=Count(
            'attendance_sheets__records',
            filter=Q(attendance_sheets__records__presente=False),
            distinct=True,
        ),
    )
