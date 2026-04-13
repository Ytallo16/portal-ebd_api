from rest_framework import serializers

from .models import AttendanceRecord, AttendanceSheet


class AttendanceRecordSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='student.nome', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = ['id', 'student', 'aluno_nome', 'presente']


class AttendanceSheetSerializer(serializers.ModelSerializer):
    records = AttendanceRecordSerializer(many=True, read_only=True)

    class Meta:
        model = AttendanceSheet
        fields = [
            'id',
            'lesson',
            'class_group',
            'professor',
            'visitantes',
            'biblias',
            'revistas',
            'oferta_valor',
            'finalized_at',
            'records',
        ]


class AttendanceBulkUpsertSerializer(serializers.Serializer):
    records = serializers.ListField(child=serializers.DictField(), allow_empty=False)
