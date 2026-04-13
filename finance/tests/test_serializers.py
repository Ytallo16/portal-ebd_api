from datetime import date

from django.test import TestCase

from finance.serializers import OfferingSerializer


class OfferingSerializerTests(TestCase):
    def test_negative_value_is_invalid(self):
        serializer = OfferingSerializer(data={'data': date.today(), 'valor': -1, 'lesson': None, 'class_group': None})
        self.assertFalse(serializer.is_valid())
        self.assertIn('valor', serializer.errors)
