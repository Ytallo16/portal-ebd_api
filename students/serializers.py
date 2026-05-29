from rest_framework import serializers

from .models import Student, StudentAddress, StudentGuardian
from .services import turma_exige_responsavel


class StudentGuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentGuardian
        fields = ['id', 'nome', 'telefone']


class StudentAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAddress
        fields = ['cep', 'rua', 'numero', 'complemento', 'bairro', 'cidade', 'uf']


class StudentSerializer(serializers.ModelSerializer):
    endereco = StudentAddressSerializer(required=False)
    responsaveis = StudentGuardianSerializer(many=True, required=False)
    turma_nome = serializers.CharField(source='class_group.nome', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id',
            'organization',
            'class_group',
            'turma_nome',
            'nome',
            'sexo',
            'data_nascimento',
            'email',
            'telefone',
            'ativo',
            'is_active',
            'endereco',
            'responsaveis',
        ]
        read_only_fields = ['organization']

    def _turma_exige_responsavel(self, instance):
        turma = instance.class_group
        if not turma:
            return False
        return turma_exige_responsavel(turma.faixa_etaria, turma.nome)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._turma_exige_responsavel(instance):
            data['responsaveis'] = []
        return data

    def _sync_responsaveis(self, student, responsaveis_data):
        student.responsaveis.all().delete()
        if not student.class_group or not turma_exige_responsavel(
            student.class_group.faixa_etaria,
            student.class_group.nome,
        ):
            return

        for responsavel in responsaveis_data:
            StudentGuardian.objects.create(student=student, **responsavel)

    def create(self, validated_data):
        endereco_data = validated_data.pop('endereco', None)
        responsaveis_data = validated_data.pop('responsaveis', [])
        student = Student.objects.create(**validated_data)

        if endereco_data:
            StudentAddress.objects.create(student=student, **endereco_data)

        if responsaveis_data and student.class_group:
            self._sync_responsaveis(student, responsaveis_data)

        return student

    def update(self, instance, validated_data):
        endereco_data = validated_data.pop('endereco', None)
        responsaveis_data = validated_data.pop('responsaveis', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if endereco_data is not None:
            StudentAddress.objects.update_or_create(student=instance, defaults=endereco_data)

        if not self._turma_exige_responsavel(instance):
            instance.responsaveis.all().delete()
        elif responsaveis_data is not None:
            self._sync_responsaveis(instance, responsaveis_data)

        return instance
