import csv
import hashlib
import io
import os
import unicodedata
from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from classrooms.models import ClassGroup

from .models import Student, StudentHistory, StudentImportBatch, StudentImportRow
from .serializers import StudentSerializer
from .services import record_student_history, student_snapshot


REQUIRED_COLUMNS = ('nome', 'sexo', 'data_nascimento', 'turma')
OPTIONAL_COLUMNS = (
    'email',
    'telefone',
    'cep',
    'rua',
    'numero',
    'complemento',
    'bairro',
    'cidade',
    'uf',
    'responsavel_nome',
    'responsavel_telefone',
)
KNOWN_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_ROWS = 5000


class ImportBatchConflict(Exception):
    pass


def _normalize(value):
    text = unicodedata.normalize('NFKD', str(value or '').strip())
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return '_'.join(text.lower().replace('-', ' ').split())


def _parse_date(value):
    for date_format in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError('use AAAA-MM-DD ou DD/MM/AAAA')


def _parse_sex(value):
    normalized = _normalize(value)
    mapping = {
        'm': 'M',
        'masculino': 'M',
        'f': 'F',
        'feminino': 'F',
    }
    if normalized not in mapping:
        raise ValueError('use M, F, Masculino ou Feminino')
    return mapping[normalized]


def _flatten_errors(errors, prefix=''):
    messages = []
    for field, details in errors.items():
        label = f'{prefix}.{field}' if prefix else field
        if isinstance(details, dict):
            messages.extend(_flatten_errors(details, label))
        elif isinstance(details, list):
            for detail in details:
                if isinstance(detail, dict):
                    messages.extend(_flatten_errors(detail, label))
                else:
                    messages.append(f'{label}: {detail}')
        else:
            messages.append(f'{label}: {details}')
    return messages


def _decode_raw(raw, file_errors):
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    file_errors.append('Não foi possível ler o arquivo. Salve-o como CSV UTF-8.')
    return None


def _get_dialect(content):
    sample = content[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=',;\t|')
    except csv.Error:
        return csv.excel


def _row_response(row):
    response_status = {
        StudentImportRow.STATUS_VALID: 'VALIDO',
        StudentImportRow.STATUS_INVALID: 'INVALIDO',
        StudentImportRow.STATUS_CREATED: 'CADASTRADO',
        StudentImportRow.STATUS_FAILED: 'NAO_CADASTRADO',
        StudentImportRow.STATUS_UNDONE: 'DESFEITO',
        StudentImportRow.STATUS_UNDO_SKIPPED: 'NAO_DESFEITO',
    }[row.status]
    return {
        'linha': row.row_number,
        'nome': row.name or 'Não informado',
        'status': response_status,
        'motivos': row.errors,
        'aluno_id': row.student_id,
    }


def serialize_import_batch(batch, *, phase=None):
    rows = list(batch.rows.all())
    created = sum(row.status == StudentImportRow.STATUS_CREATED for row in rows)
    failed = sum(row.status == StudentImportRow.STATUS_FAILED for row in rows)
    undone = sum(row.status == StudentImportRow.STATUS_UNDONE for row in rows)
    undo_skipped = sum(row.status == StudentImportRow.STATUS_UNDO_SKIPPED for row in rows)
    if phase is None:
        if batch.status in (
            StudentImportBatch.STATUS_UNDONE,
            StudentImportBatch.STATUS_PARTIALLY_UNDONE,
        ):
            phase = 'DESFAZIMENTO'
        elif batch.status == StudentImportBatch.STATUS_CONFIRMED:
            phase = 'CONFIRMACAO'
        else:
            phase = 'VALIDACAO'

    return {
        'fase': phase,
        'lote_id': str(batch.public_id),
        'status_lote': batch.status,
        'arquivo_nome': batch.original_filename,
        'total_linhas': batch.total_rows,
        'validos': batch.valid_rows,
        'invalidos': batch.invalid_rows,
        'cadastrados': created,
        'nao_cadastrados': batch.invalid_rows + failed,
        'desativados': undone,
        'nao_desfeitos': undo_skipped,
        'colunas_obrigatorias': list(REQUIRED_COLUMNS),
        'colunas_ausentes': batch.missing_columns,
        'colunas_ignoradas': batch.ignored_columns,
        'erros_arquivo': batch.file_errors,
        'pode_confirmar': (
            batch.status == StudentImportBatch.STATUS_VALIDATED and batch.valid_rows > 0
        ),
        'pode_desfazer': (
            batch.status == StudentImportBatch.STATUS_CONFIRMED
            and batch.created_students > 0
        ),
        'criado_em': batch.created_at,
        'confirmado_em': batch.confirmed_at,
        'desfeito_em': batch.undone_at,
        'resultados': [_row_response(row) for row in rows],
    }


def serialize_import_batch_summary(batch):
    return {
        'lote_id': str(batch.public_id),
        'arquivo_nome': batch.original_filename,
        'status_lote': batch.status,
        'total_linhas': batch.total_rows,
        'validos': batch.valid_rows,
        'invalidos': batch.invalid_rows,
        'cadastrados': batch.created_students,
        'pode_confirmar': (
            batch.status == StudentImportBatch.STATUS_VALIDATED and batch.valid_rows > 0
        ),
        'pode_desfazer': (
            batch.status == StudentImportBatch.STATUS_CONFIRMED
            and batch.created_students > 0
        ),
        'criado_em': batch.created_at,
        'confirmado_em': batch.confirmed_at,
        'desfeito_em': batch.undone_at,
        'criado_por': batch.created_by.nome if batch.created_by else None,
        'confirmado_por': batch.confirmed_by.nome if batch.confirmed_by else None,
        'desfeito_por': batch.undone_by.nome if batch.undone_by else None,
    }


def _available_classes(organization, allowed_class_ids):
    classes = ClassGroup.objects.filter(
        organization=organization,
        ativa=True,
        is_active=True,
    )
    if allowed_class_ids is not None:
        classes = classes.filter(id__in=allowed_class_ids)
    return classes


def validate_students_csv(*, uploaded_file, organization, user, allowed_class_ids=None):
    raw = uploaded_file.read()
    file_errors = []
    if len(raw) > MAX_FILE_SIZE:
        file_errors.append('O arquivo excede o limite de 5 MB.')

    batch = StudentImportBatch.objects.create(
        organization=organization,
        created_by=user,
        original_filename=os.path.basename(uploaded_file.name or 'alunos.csv')[:255],
        file_sha256=hashlib.sha256(raw).hexdigest(),
        file_size=len(raw),
        status=StudentImportBatch.STATUS_INVALID,
        file_errors=file_errors,
    )
    if file_errors:
        return serialize_import_batch(batch, phase='VALIDACAO')

    content = _decode_raw(raw, file_errors)
    if content is None:
        batch.file_errors = file_errors
        batch.save(update_fields=['file_errors', 'updated_at'])
        return serialize_import_batch(batch, phase='VALIDACAO')

    reader = csv.reader(io.StringIO(content), dialect=_get_dialect(content))
    try:
        raw_headers = next(reader)
    except StopIteration:
        batch.file_errors = ['O arquivo está vazio.']
        batch.save(update_fields=['file_errors', 'updated_at'])
        return serialize_import_batch(batch, phase='VALIDACAO')

    headers = [_normalize(header) for header in raw_headers]
    if not any(headers):
        batch.file_errors = ['O arquivo não possui cabeçalho.']
        batch.save(update_fields=['file_errors', 'updated_at'])
        return serialize_import_batch(batch, phase='VALIDACAO')
    if len(headers) != len(set(headers)):
        duplicated = sorted({header for header in headers if headers.count(header) > 1})
        batch.file_errors = [
            f'Existem colunas repetidas no cabeçalho: {", ".join(duplicated)}.'
        ]
        batch.save(update_fields=['file_errors', 'updated_at'])
        return serialize_import_batch(batch, phase='VALIDACAO')

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in headers]
    ignored_columns = [
        raw_headers[index].strip()
        for index, header in enumerate(headers)
        if header not in KNOWN_COLUMNS
    ]
    batch.missing_columns = missing_columns
    batch.ignored_columns = ignored_columns
    if missing_columns:
        batch.file_errors = [
            'Faltam colunas obrigatórias: ' + ', '.join(missing_columns) + '.'
        ]
        batch.save(
            update_fields=[
                'missing_columns',
                'ignored_columns',
                'file_errors',
                'updated_at',
            ]
        )
        return serialize_import_batch(batch, phase='VALIDACAO')

    classes_by_name = {}
    for class_group in _available_classes(organization, allowed_class_ids):
        classes_by_name.setdefault(_normalize(class_group.nome), []).append(class_group)

    import_rows = []
    seen_students = set()
    for values in reader:
        if not any(str(value).strip() for value in values):
            continue
        if len(import_rows) >= MAX_ROWS:
            file_errors.append(
                f'O limite de {MAX_ROWS} alunos por arquivo foi atingido; '
                'as demais linhas não foram avaliadas.'
            )
            break

        row = {
            header: (values[index].strip() if index < len(values) else '')
            for index, header in enumerate(headers)
        }
        reasons = []
        if len(values) > len(headers):
            reasons.append('A linha possui mais valores do que o cabeçalho.')
        for column in REQUIRED_COLUMNS:
            if not row.get(column):
                reasons.append(f'{column}: valor obrigatório não informado')

        birth_date = None
        sex = None
        if row.get('data_nascimento'):
            try:
                birth_date = _parse_date(row['data_nascimento'])
            except ValueError as error:
                reasons.append(f'data_nascimento: {error}')
        if row.get('sexo'):
            try:
                sex = _parse_sex(row['sexo'])
            except ValueError as error:
                reasons.append(f'sexo: {error}')

        class_group = None
        if row.get('turma'):
            matching_classes = classes_by_name.get(_normalize(row['turma']), [])
            if not matching_classes:
                reasons.append('turma: não encontrada, inativa ou sem acesso para este usuário')
            elif len(matching_classes) > 1:
                reasons.append('turma: nome ambíguo; renomeie uma das turmas antes de importar')
            else:
                class_group = matching_classes[0]

        if row.get('nome') and birth_date:
            identity = (_normalize(row['nome']), birth_date.isoformat())
            if identity in seen_students:
                reasons.append('aluno: repetido neste mesmo arquivo')
            else:
                seen_students.add(identity)

            existing = Student.objects.filter(
                organization=organization,
                nome__iexact=row['nome'],
                data_nascimento=birth_date,
            )
            if existing.filter(is_active=True).exists():
                reasons.append(
                    'aluno: já existe nesta igreja com o mesmo nome e data de nascimento'
                )
            elif existing.filter(is_active=False).exists():
                reasons.append(
                    'aluno: existe inativo nesta igreja; restaure o cadastro em vez de duplicá-lo'
                )

        address = {
            column: row[column]
            for column in ('cep', 'rua', 'numero', 'complemento', 'bairro', 'cidade', 'uf')
            if row.get(column)
        }
        guardians = []
        if row.get('responsavel_nome') or row.get('responsavel_telefone'):
            if not row.get('responsavel_nome'):
                reasons.append(
                    'responsavel_nome: informe o nome quando houver telefone do responsável'
                )
            else:
                guardians.append(
                    {
                        'nome': row['responsavel_nome'],
                        'telefone': row.get('responsavel_telefone', ''),
                    }
                )

        payload = {}
        if class_group and birth_date and sex and row.get('nome'):
            payload = {
                'class_group': class_group.id,
                'nome': row['nome'],
                'sexo': sex,
                'data_nascimento': birth_date.isoformat(),
                'email': row.get('email', ''),
                'telefone': row.get('telefone', ''),
            }
            if address:
                payload['endereco'] = address
            if guardians:
                payload['responsaveis'] = guardians

            serializer = StudentSerializer(
                data=payload,
                context={'organization': organization},
            )
            if not reasons and not serializer.is_valid():
                reasons.extend(_flatten_errors(serializer.errors))

        import_rows.append(
            StudentImportRow(
                batch=batch,
                row_number=reader.line_num,
                name=row.get('nome', ''),
                status=(
                    StudentImportRow.STATUS_INVALID
                    if reasons
                    else StudentImportRow.STATUS_VALID
                ),
                payload=payload,
                errors=reasons,
            )
        )

    if not import_rows and not file_errors:
        file_errors.append('O arquivo não possui linhas de alunos.')

    StudentImportRow.objects.bulk_create(import_rows)
    batch.total_rows = len(import_rows)
    batch.valid_rows = sum(
        row.status == StudentImportRow.STATUS_VALID for row in import_rows
    )
    batch.invalid_rows = batch.total_rows - batch.valid_rows
    batch.file_errors = file_errors
    batch.status = StudentImportBatch.STATUS_VALIDATED
    batch.save(
        update_fields=[
            'total_rows',
            'valid_rows',
            'invalid_rows',
            'ignored_columns',
            'missing_columns',
            'file_errors',
            'status',
            'updated_at',
        ]
    )
    return serialize_import_batch(batch, phase='VALIDACAO')


def _validate_payload_for_confirmation(*, payload, organization, allowed_class_ids):
    reasons = []
    class_id = payload.get('class_group')
    available_class = _available_classes(organization, allowed_class_ids).filter(
        id=class_id
    ).first()
    if not available_class:
        reasons.append('turma: ficou inativa ou o usuário não possui mais acesso')

    birth_date = payload.get('data_nascimento')
    existing = Student.objects.filter(
        organization=organization,
        nome__iexact=payload.get('nome', ''),
        data_nascimento=birth_date,
    )
    if existing.filter(is_active=True).exists():
        reasons.append('aluno: foi cadastrado depois da validação deste arquivo')
    elif existing.filter(is_active=False).exists():
        reasons.append('aluno: existe inativo; restaure o cadastro em vez de duplicá-lo')

    serializer = StudentSerializer(
        data=payload,
        context={'organization': organization},
    )
    if not reasons and not serializer.is_valid():
        reasons.extend(_flatten_errors(serializer.errors))
    return serializer, reasons


@transaction.atomic
def confirm_students_import(*, batch, organization, user, allowed_class_ids=None):
    batch = (
        StudentImportBatch.objects.select_for_update()
        .filter(pk=batch.pk, organization=organization)
        .first()
    )
    if not batch:
        raise StudentImportBatch.DoesNotExist
    if batch.status == StudentImportBatch.STATUS_CONFIRMED:
        return serialize_import_batch(batch, phase='CONFIRMACAO')
    if batch.status != StudentImportBatch.STATUS_VALIDATED:
        raise ImportBatchConflict('Este lote não está disponível para confirmação.')

    created_count = 0
    rows = list(batch.rows.select_for_update().order_by('row_number'))
    for row in rows:
        if row.status != StudentImportRow.STATUS_VALID:
            continue

        serializer, reasons = _validate_payload_for_confirmation(
            payload=row.payload,
            organization=organization,
            allowed_class_ids=allowed_class_ids,
        )
        if reasons:
            row.status = StudentImportRow.STATUS_FAILED
            row.errors = reasons
            row.save(update_fields=['status', 'errors'])
            continue

        try:
            with transaction.atomic():
                student = serializer.save(
                    organization=organization,
                    created_by=user,
                )
        except IntegrityError:
            row.status = StudentImportRow.STATUS_FAILED
            row.errors = [
                'Não foi possível gravar o aluno por conflito com dados existentes.'
            ]
            row.save(update_fields=['status', 'errors'])
            continue

        record_student_history(
            student=student,
            action=StudentHistory.ACTION_IMPORTED,
            actor=user,
            metadata={
                'lote_id': str(batch.public_id),
                'linha': row.row_number,
                'arquivo': batch.original_filename,
            },
        )
        row.status = StudentImportRow.STATUS_CREATED
        row.student = student
        row.student_version_at_confirm = student.updated_at
        row.errors = []
        row.save(
            update_fields=[
                'status',
                'student',
                'student_version_at_confirm',
                'errors',
            ]
        )
        created_count += 1

    batch.status = StudentImportBatch.STATUS_CONFIRMED
    batch.created_students = created_count
    batch.confirmed_at = timezone.now()
    batch.confirmed_by = user
    batch.updated_by = user
    batch.save(
        update_fields=[
            'status',
            'created_students',
            'confirmed_at',
            'confirmed_by',
            'updated_by',
            'updated_at',
        ]
    )
    return serialize_import_batch(batch, phase='CONFIRMACAO')


@transaction.atomic
def undo_students_import(*, batch, organization, user):
    batch = (
        StudentImportBatch.objects.select_for_update()
        .filter(pk=batch.pk, organization=organization)
        .first()
    )
    if not batch:
        raise StudentImportBatch.DoesNotExist
    if batch.status in (
        StudentImportBatch.STATUS_UNDONE,
        StudentImportBatch.STATUS_PARTIALLY_UNDONE,
    ):
        return serialize_import_batch(batch, phase='DESFAZIMENTO')
    if batch.status != StudentImportBatch.STATUS_CONFIRMED:
        raise ImportBatchConflict('Somente uma importação confirmada pode ser desfeita.')

    skipped = 0
    rows = list(
        batch.rows.select_for_update()
        .filter(status=StudentImportRow.STATUS_CREATED)
        .order_by('row_number')
    )
    for row in rows:
        student = (
            Student.objects.select_for_update()
            .filter(pk=row.student_id, organization=organization)
            .first()
        )
        reason = None
        if not student:
            reason = 'Aluno não encontrado; nenhuma alteração foi feita.'
        elif not student.is_active:
            reason = 'Aluno já estava inativo; nenhuma alteração foi feita.'
        elif student.updated_at != row.student_version_at_confirm:
            reason = (
                'Aluno alterado após a importação; restaure os dados manualmente antes '
                'de decidir pela inativação.'
            )

        if reason:
            row.status = StudentImportRow.STATUS_UNDO_SKIPPED
            row.errors = [reason]
            row.save(update_fields=['status', 'errors'])
            skipped += 1
            continue

        before = student_snapshot(student)
        student.is_active = False
        student.ativo = False
        student.deleted_at = timezone.now()
        student.updated_by = user
        student.save(
            update_fields=[
                'is_active',
                'ativo',
                'deleted_at',
                'updated_by',
                'updated_at',
            ]
        )
        record_student_history(
            student=student,
            action=StudentHistory.ACTION_IMPORT_UNDONE,
            actor=user,
            before=before,
            metadata={
                'lote_id': str(batch.public_id),
                'linha': row.row_number,
                'arquivo': batch.original_filename,
                'frequencias_preservadas': True,
            },
        )
        row.status = StudentImportRow.STATUS_UNDONE
        row.errors = []
        row.save(update_fields=['status', 'errors'])

    batch.status = (
        StudentImportBatch.STATUS_PARTIALLY_UNDONE
        if skipped
        else StudentImportBatch.STATUS_UNDONE
    )
    batch.undone_at = timezone.now()
    batch.undone_by = user
    batch.updated_by = user
    batch.save(
        update_fields=[
            'status',
            'undone_at',
            'undone_by',
            'updated_by',
            'updated_at',
        ]
    )
    return serialize_import_batch(batch, phase='DESFAZIMENTO')
