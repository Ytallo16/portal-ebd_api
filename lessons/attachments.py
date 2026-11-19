"""Regras de validação dos anexos de lição (puras, sem ORM)."""
from pathlib import Path

from rest_framework.exceptions import ValidationError

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = frozenset(
    [
        '.pdf',
        '.doc',
        '.docx',
        '.ppt',
        '.pptx',
        '.xls',
        '.xlsx',
        '.txt',
        '.jpg',
        '.jpeg',
        '.png',
        '.webp',
        '.mp3',
        '.zip',
    ]
)


def get_extension(filename):
    return Path(filename or '').suffix.lower()


def validate_attachment_file(arquivo):
    """Levanta ValidationError se o arquivo não puder ser anexado."""
    extensao = get_extension(getattr(arquivo, 'name', ''))

    if extensao not in ALLOWED_EXTENSIONS:
        permitidas = ', '.join(sorted(ALLOWED_EXTENSIONS))
        raise ValidationError(
            {'arquivo': f'Formato não permitido. Aceitos: {permitidas}.'}
        )

    tamanho = getattr(arquivo, 'size', 0) or 0

    if tamanho <= 0:
        raise ValidationError({'arquivo': 'O arquivo está vazio.'})

    if tamanho > MAX_ATTACHMENT_BYTES:
        raise ValidationError({'arquivo': 'O arquivo excede o limite de 5 MB.'})
