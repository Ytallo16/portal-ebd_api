from rest_framework import serializers

from .attachments import validate_attachment_file
from .models import LessonAttachment


class LessonAttachmentSerializer(serializers.ModelSerializer):
    arquivo = serializers.FileField(write_only=True)
    arquivo_url = serializers.SerializerMethodField()
    autor_nome = serializers.SerializerMethodField()
    pode_excluir = serializers.SerializerMethodField()

    class Meta:
        model = LessonAttachment
        fields = [
            'id',
            'lesson',
            'arquivo',
            'arquivo_url',
            'nome_original',
            'descricao',
            'tamanho',
            'content_type',
            'autor_nome',
            'pode_excluir',
            'created_at',
        ]
        read_only_fields = [
            'nome_original',
            'tamanho',
            'content_type',
            'created_at',
        ]

    def validate_arquivo(self, value):
        validate_attachment_file(value)
        return value

    def get_arquivo_url(self, obj):
        if not obj.arquivo:
            return None
        request = self.context.get('request')
        url = obj.arquivo.url
        return request.build_absolute_uri(url) if request else url

    def get_autor_nome(self, obj):
        return obj.created_by.nome if obj.created_by_id else ''

    def get_pode_excluir(self, obj):
        from .services import can_delete_lesson_attachment

        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return can_delete_lesson_attachment(request.user, obj)
