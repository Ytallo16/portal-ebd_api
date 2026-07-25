from django.urls import path

from .views import (
    actions,
    attendance_evolution,
    birthdays,
    class_composition,
    offering_evolution,
    professor_dashboard,
    professor_ranking,
    summary,
)

urlpatterns = [
    path('dashboard/actions', actions),
    path('dashboard/summary', summary),
    path('dashboard/attendance-evolution', attendance_evolution),
    path('dashboard/offering-evolution', offering_evolution),
    path('dashboard/class-composition', class_composition),
    path('dashboard/birthdays', birthdays),
    path('dashboard/professor', professor_dashboard),
    path('dashboard/professor-ranking', professor_ranking),
]
