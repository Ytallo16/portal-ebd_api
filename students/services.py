import re
import unicodedata


def _normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(ch for ch in texto if unicodedata.category(ch) != 'Mn')
    return texto.lower()


def turma_exige_responsavel(faixa_etaria: str, nome_turma: str = '') -> bool:
    """Turmas infantis/crianças exigem responsável; adultos e jovens não."""
    text = _normalizar_texto(f'{faixa_etaria} {nome_turma}')

    if re.search(
        r'adulto|jovem|adolescente|familia|terceira idade|discipulado|novos convertidos',
        text,
    ):
        return False

    if re.search(r'crianca|berc|jardim|primari|junior|infantil|bercario', text):
        return True

    faixa = re.search(r'(\d+)\s*[-–]\s*(\d+)', text)
    if faixa:
        return int(faixa.group(2)) <= 12

    return False
