from django.urls import path

from .views import (
    attendance_evolution,
    birthdays,
    class_composition,
    offering_evolution,
    professor_dashboard,
    summary,
)

urlpatterns = [
    path('dashboard/summary', summary),
    path('dashboard/attendance-evolution', attendance_evolution),
    path('dashboard/offering-evolution', offering_evolution),
    path('dashboard/class-composition', class_composition),
    path('dashboard/birthdays', birthdays),
    path('dashboard/professor', professor_dashboard),
]
