from rest_framework import serializers

from access_control.models import UserRole
from lessons.models import Lesson

from .models import ClassGroup, ClassTeacher


class ClassTeacherSerializer(serializers.ModelSerializer):
    user_nome = serializers.CharField(source='user.nome', read_only=True)

    class Meta:
        model = ClassTeacher
        fields = ['id', 'class_group', 'user', 'user_nome']
        read_only_fields = ['id']

    def validate(self, attrs):
        class_group = attrs.get('class_group') or getattr(self.instance, 'class_group', None)
        user = attrs.get('user') or getattr(self.instance, 'user', None)
        if class_group and user:
            exists = ClassTeacher.objects.filter(class_group=class_group, user=user)
            if self.instance:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                raise serializers.ValidationError({'user': 'Este professor já está vinculado à turma.'})

            is_professor = UserRole.objects.filter(
                user=user,
                ativo=True,
                role__nome='PROFESSOR',
                organization=class_group.organization,
            ).exists()
            if not is_professor:
                raise serializers.ValidationError({'user': 'O usuário selecionado não é professor desta igreja.'})
        return attrs


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
