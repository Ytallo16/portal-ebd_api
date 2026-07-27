from urllib.parse import unquote

from django.db import DatabaseError

from .models import ActivityLog


RESOURCE_LABELS = {
    'users': ('usuário', 'Usuários'),
    'organizations': ('organização', 'Organizações'),
    'organization-memberships': ('vínculo com organização', 'Organizações'),
    'roles': ('perfil de acesso', 'Permissões'),
    'permissions': ('permissão', 'Permissões'),
    'classes': ('turma', 'Turmas'),
    'class-teachers': ('vínculo de professor', 'Turmas'),
    'students': ('aluno', 'Alunos'),
    'lessons': ('lição', 'Lições'),
    'trimesters': ('trimestre', 'Lições'),
    'lesson-schedules': ('escala de aula', 'Lições'),
    'attendance': ('registro de frequência', 'Frequência'),
    'attendance-sheets': ('registro de frequência', 'Frequência'),
    'offerings': ('oferta', 'Financeiro'),
    'finance': ('lançamento financeiro', 'Financeiro'),
    'publication-controls': ('controle de revista', 'Revistas'),
    'notifications': ('notificação', 'Notificações'),
    'me': ('perfil pessoal', 'Conta'),
}

CUSTOM_ACTIONS = {
    'activate': 'Ativou',
    'deactivate': 'Desativou',
    'restore': 'Restaurou',
    'toggle-active': 'Alterou a situação de',
    'reset-password': 'Redefiniu a senha de',
    'change-password': 'Alterou a própria senha',
    'context': 'Alterou a organização ativa',
    'confirm': 'Confirmou',
    'undo': 'Desfez',
    'sync': 'Sincronizou',
    'finalize': 'Finalizou',
    'import': 'Importou',
    'imports': 'Processou importação de',
    'avatar': 'Alterou a foto do perfil',
    'logout': 'Encerrou a sessão',
}

METHOD_ACTIONS = {
    'POST': 'Criou',
    'PUT': 'Atualizou',
    'PATCH': 'Atualizou',
    'DELETE': 'Excluiu',
}


def _path_parts(path):
    clean_path = unquote(path).split('?', 1)[0].strip('/')
    parts = clean_path.split('/')
    if parts[:2] == ['api', 'v1']:
        parts = parts[2:]
    return [part for part in parts if part]


def describe_activity(method, path):
    parts = _path_parts(path)
    if not parts:
        return 'Executou uma operação', 'Sistema', ''

    if parts[:2] == ['auth', 'logout']:
        return 'Encerrou a sessão', 'Conta', ''

    resource_key = next(
        (part for part in reversed(parts) if part in RESOURCE_LABELS),
        parts[0],
    )
    resource_singular, resource_group = RESOURCE_LABELS.get(
        resource_key,
        (resource_key.replace('-', ' '), resource_key.replace('-', ' ').title()),
    )

    custom_key = next((part for part in reversed(parts) if part in CUSTOM_ACTIONS), None)
    if custom_key:
        verb = CUSTOM_ACTIONS[custom_key]
        if custom_key in ('change-password', 'context', 'avatar', 'logout'):
            action = verb
        else:
            action = f'{verb} {resource_singular}'
    else:
        verb = METHOD_ACTIONS.get(method.upper(), 'Executou operação em')
        action = f'{verb} {resource_singular}'

    object_reference = ''
    for index, part in enumerate(parts):
        if part != resource_key or index + 1 >= len(parts):
            continue
        candidate = parts[index + 1]
        if candidate.isdigit():
            object_reference = f'ID {candidate}'
        break

    return action, resource_group, object_reference


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',', 1)[0].strip() or None
    return request.META.get('REMOTE_ADDR') or None


def record_activity(
    *,
    request,
    user,
    organization,
    action,
    resource,
    status_code,
    object_reference='',
    event_type='REQUEST',
    model_label='',
    changes=None,
):
    if organization is None:
        return
    try:
        ActivityLog.objects.create(
            organization=organization,
            actor=user,
            actor_name=(user.nome or user.get_username() or 'Usuário')[:255],
            actor_email=(user.email or '')[:254],
            action=action,
            resource=resource,
            object_reference=object_reference,
            event_type=event_type,
            model_label=model_label,
            changes=changes or {},
            method=request.method,
            path=request.path[:500],
            status_code=status_code,
            succeeded=200 <= status_code < 400,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )
    except DatabaseError:
        # Auditoria não pode impedir autenticação ou outra operação do sistema.
        return
