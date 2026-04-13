from rest_framework import serializers

from lessons.models import Lesson

from .models import ClassGroup, ClassTeacher


class ClassTeacherSerializer(serializers.ModelSerializer):
    user_nome = serializers.CharField(source='user.nome', read_only=True)

    class Meta:
        model = ClassTeacher
        fields = ['id', 'user', 'user_nome']


class ClassGroupSerializer(serializers.ModelSerializer):
    professores = ClassTeacherSerializer(source='teachers', many=True, read_only=True)
    total_alunos = serializers.IntegerField(read_only=True)

    class Meta:
        model = ClassGroup
        fields = [
            'id',
            'organization',
            'nome',
            'faixa_etaria',
            'cor',
            'ativa',
            'is_active',
            'total_alunos',
            'professores',
        ]
        read_only_fields = ['organization']


class ClassLessonsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'numero', 'tema', 'data', 'status', 'trimestre', 'ano']
