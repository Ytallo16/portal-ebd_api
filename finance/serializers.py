from rest_framework import serializers

from .models import Offering


class OfferingSerializer(serializers.ModelSerializer):
    turma_nome = serializers.CharField(source='class_group.nome', read_only=True)
    licao_tema = serializers.CharField(source='lesson.tema', read_only=True)

    class Meta:
        model = Offering
        fields = [
            'id',
            'organization',
            'lesson',
            'licao_tema',
            'class_group',
            'turma_nome',
            'data',
            'valor',
            'is_active',
        ]
        read_only_fields = ['organization']

    def validate_valor(self, value):
        if value < 0:
            raise serializers.ValidationError('Oferta não pode ser negativa.')
        return value

    def validate(self, attrs):
        instance = self.instance
        organization = self.context.get('organization')
        lesson = attrs.get('lesson', getattr(instance, 'lesson', None))
        class_group = attrs.get('class_group', getattr(instance, 'class_group', None))

        if instance is not None:
            if 'lesson' in attrs and attrs['lesson'] != instance.lesson:
                raise serializers.ValidationError(
                    {'lesson': 'Não é possível trocar a lição de uma oferta existente.'}
                )
            if 'class_group' in attrs and attrs['class_group'] != instance.class_group:
                raise serializers.ValidationError(
                    {'class_group': 'Não é possível trocar a turma de uma oferta existente.'}
                )

        if lesson is None and class_group is None:
            return attrs
        if lesson is None or class_group is None:
            raise serializers.ValidationError(
                {
                    'lesson': 'Lição e turma devem ser informadas juntas.',
                    'class_group': 'Lição e turma devem ser informadas juntas.',
                }
            )

        if organization is not None:
            if lesson.organization_id != organization.id:
                raise serializers.ValidationError(
                    {'lesson': 'A lição não pertence à igreja selecionada.'}
                )
            if class_group.organization_id != organization.id:
                raise serializers.ValidationError(
                    {'class_group': 'A turma não pertence à igreja selecionada.'}
                )

        if lesson.organization_id != class_group.organization_id:
            raise serializers.ValidationError(
                {'class_group': 'A turma não pertence à mesma igreja da lição.'}
            )
        if not lesson.is_active:
            raise serializers.ValidationError({'lesson': 'A lição está inativa.'})
        if not class_group.is_active or not class_group.ativa:
            raise serializers.ValidationError({'class_group': 'A turma está inativa.'})

        return attrs
