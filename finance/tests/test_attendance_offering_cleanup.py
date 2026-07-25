from datetime import date
from importlib import import_module

from django.apps import apps
from django.test import TestCase
from django.utils import timezone

from attendance.models import AttendanceSheet
from classrooms.models import ClassGroup
from finance.models import Offering
from lessons.models import Lesson
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization


class AttendanceOfferingCleanupTests(TestCase):
    def setUp(self):
        campo = Organization.objects.create(
            nome='Campo Ofertas',
            sigla='CO',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.organization = Organization.objects.create(
            nome='Igreja Ofertas',
            sigla='IO',
            tipo=TIPO_IGREJA,
            parent=campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.class_group = ClassGroup.objects.create(
            organization=self.organization,
            nome='Adultos',
            faixa_etaria='Adultos',
            cor='#125A94',
        )
        self.lesson = Lesson.objects.create(
            organization=self.organization,
            numero=1,
            tema='Oferta oficial',
            data=date(2026, 1, 4),
            revista='Adultos',
            trimestre=1,
            ano=2026,
        )
        self.sheet = AttendanceSheet.objects.create(
            lesson=self.lesson,
            class_group=self.class_group,
            oferta_valor='37.50',
            finalized_at=None,
        )
        self.offering = Offering.objects.create(
            organization=self.organization,
            lesson=self.lesson,
            class_group=self.class_group,
            data=self.lesson.data,
            valor='99.00',
        )

    def _run_repair(self):
        migration = import_module(
            'finance.migrations.0002_cleanup_attendance_offerings'
        )
        migration.repair_attendance_offerings(apps, None)

    def test_repair_deactivates_draft_and_is_idempotent_when_completed(self):
        self._run_repair()

        self.offering.refresh_from_db()
        self.assertFalse(self.offering.is_active)
        self.assertIsNotNone(self.offering.deleted_at)

        self.sheet.finalized_at = timezone.now()
        self.sheet.save(update_fields=['finalized_at', 'updated_at'])
        self._run_repair()
        self._run_repair()

        self.offering.refresh_from_db()
        self.assertTrue(self.offering.is_active)
        self.assertIsNone(self.offering.deleted_at)
        self.assertEqual(str(self.offering.valor), '37.50')
        self.assertEqual(
            Offering.objects.filter(
                organization=self.organization,
                lesson=self.lesson,
                class_group=self.class_group,
            ).count(),
            1,
        )
