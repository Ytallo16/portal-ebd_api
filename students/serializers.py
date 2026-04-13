from rest_framework import serializers

from .models import Student, StudentAddress, StudentGuardian


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

    def create(self, validated_data):
        endereco_data = validated_data.pop('endereco', None)
        responsaveis_data = validated_data.pop('responsaveis', [])
        student = Student.objects.create(**validated_data)

        if endereco_data:
            StudentAddress.objects.create(student=student, **endereco_data)

        for responsavel in responsaveis_data:
            StudentGuardian.objects.create(student=student, **responsavel)

        return student

    def update(self, instance, validated_data):
        endereco_data = validated_data.pop('endereco', None)
        responsaveis_data = validated_data.pop('responsaveis', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if endereco_data is not None:
            StudentAddress.objects.update_or_create(student=instance, defaults=endereco_data)

        if responsaveis_data is not None:
            instance.responsaveis.all().delete()
            for responsavel in responsaveis_data:
                StudentGuardian.objects.create(student=instance, **responsavel)

        return instance
