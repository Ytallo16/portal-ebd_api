import re
import unicodedata

from .models import StudentAddress, StudentHistory


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


def student_snapshot(student):
    try:
        address = student.endereco
    except StudentAddress.DoesNotExist:
        address = None

    return {
        'nome': student.nome,
        'sexo': student.sexo,
        'data_nascimento': student.data_nascimento.isoformat(),
        'email': student.email,
        'telefone': student.telefone,
        'class_group_id': student.class_group_id,
        'class_group_nome': student.class_group.nome if student.class_group else None,
        'is_active': student.is_active,
        'ativo': student.ativo,
        'endereco': (
            {
                'cep': address.cep,
                'rua': address.rua,
                'numero': address.numero,
                'complemento': address.complemento,
                'bairro': address.bairro,
                'cidade': address.cidade,
                'uf': address.uf,
            }
            if address
            else {}
        ),
        'responsaveis': [
            {'nome': guardian.nome, 'telefone': guardian.telefone}
            for guardian in student.responsaveis.all().order_by('id')
        ],
    }


def student_changes(before, after):
    return {
        field: {'antes': before.get(field), 'depois': after.get(field)}
        for field in sorted(set(before) | set(after))
        if before.get(field) != after.get(field)
    }


def record_student_history(
    *,
    student,
    action,
    actor,
    before=None,
    metadata=None,
):
    snapshot = student_snapshot(student)
    return StudentHistory.objects.create(
        student=student,
        organization=student.organization,
        action=action,
        actor=actor,
        changes=student_changes(before or {}, snapshot) if before is not None else {},
        snapshot=snapshot,
        metadata=metadata or {},
    )
