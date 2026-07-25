from rest_framework import serializers

from attendance.models import AttendanceRecord

from .models import Lesson, Trimester


class TrimesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trimester
        fields = [
            'id',
            'organization',
            'numero',
            'ano',
            'titulo',
            'data_inicio',
            'data_fim',
            'quantidade_licoes',
            'status',
            'is_active',
        ]
        read_only_fields = ['organization']


class LessonSerializer(serializers.ModelSerializer):
    presentes = serializers.SerializerMethodField()
    ausentes = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id',
            'organization',
            'numero',
            'tema',
            'data',
            'revista',
            'texto_aureo',
            'texto_biblico',
            'objetivo',
            'status',
            'trimestre',
            'ano',
            'presentes',
            'ausentes',
            'is_active',
        ]
        read_only_fields = ['organization']

    def get_presentes(self, obj):
        if hasattr(obj, 'total_presentes'):
            return obj.total_presentes
        return AttendanceRecord.objects.filter(attendance_sheet__lesson=obj, presente=True).count()

    def get_ausentes(self, obj):
        if hasattr(obj, 'total_ausentes'):
            return obj.total_ausentes
        return AttendanceRecord.objects.filter(attendance_sheet__lesson=obj, presente=False).count()
