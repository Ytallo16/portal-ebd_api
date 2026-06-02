from access_control.constants import (
    ADMIN_ROLES,
    FULL_OPERATIONAL_ROLES,
    OPERATIONAL_ORG_TYPES,
    OPERATIONAL_ORG_TYPES_LEGACY,
    ROLE_ADMINISTRADOR,
    ROLE_PROFESSOR,
    ROLE_SECRETARIO_CAMPO,
    ROLE_SECRETARIO_IGREJA,
)
from access_control.models import UserRole
from organizations.constants import FORMATO_IGREJA_INDIVIDUAL, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization


def normalize_tipo(tipo):
    if tipo == 'SEDE':
        return TIPO_CAMPO
    if tipo in ('FILIAL', 'CONGREGACAO'):
        return TIPO_IGREJA
    return tipo


def is_campo_organization(org):
    return normalize_tipo(org.tipo) == TIPO_CAMPO


def is_igreja_organization(org):
    return normalize_tipo(org.tipo) == TIPO_IGREJA


def is_igreja_individual(org):
    return is_igreja_organization(org) and not org.parent_id and org.formato == FORMATO_IGREJA_INDIVIDUAL


def is_organization_contract_active(org):
    """Contrato ativo: campo próprio ou igreja + campo pai ativos."""
    if org is None:
        return False
    if not org.is_active:
        return False
    if is_campo_organization(org):
        return True
    if is_igreja_organization(org) and org.parent_id:
        parent = org.parent if hasattr(org, 'parent') and org.parent_id else None
        if parent is None:
            parent = Organization.objects.filter(id=org.parent_id).first()
        return bool(parent and parent.is_active)
    return True


def filter_organizations_with_active_contract(queryset):
    orgs = list(queryset.select_related('parent'))
    return [org for org in orgs if is_organization_contract_active(org)]


def get_campo_root(org):
    current = org
    while current.parent_id:
        current = current.parent
    return current


def get_org_descendant_ids(org, include_self=True):
    ids = [org.id] if include_self else []
    queue = [org.id]
    while queue:
        children = list(
            Organization.objects.filter(parent_id__in=queue, is_active=True).values_list('id', flat=True)
        )
        ids.extend(children)
        queue = children
    return ids


def get_org_child_ids(org):
    return get_org_descendant_ids(org, include_self=False)


def get_igrejas_do_campo(campo_org, include_inactive=False):
    queryset = Organization.objects.filter(parent=campo_org, tipo=TIPO_IGREJA).select_related('parent')
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return queryset.order_by('nome')


def is_operational_organization(org):
    tipo = normalize_tipo(org.tipo)
    return tipo in OPERATIONAL_ORG_TYPES or org.tipo in OPERATIONAL_ORG_TYPES_LEGACY


def get_user_role_names(user):
    return {
        user_role.role.nome.upper()
        for user_role in user.user_roles.select_related('role').filter(ativo=True)
    }


def get_creatable_user_roles(user):
    from access_control.constants import CANONICAL_ROLES

    if is_admin_sistema(user):
        return set(CANONICAL_ROLES)

    role_names = get_user_role_names(user)
    if ROLE_SECRETARIO_CAMPO in role_names:
        return {ROLE_SECRETARIO_CAMPO, ROLE_SECRETARIO_IGREJA, ROLE_PROFESSOR}
    if ROLE_SECRETARIO_IGREJA in role_names:
        return {ROLE_SECRETARIO_IGREJA, ROLE_PROFESSOR}
    return set()


def is_admin_sistema(user):
    if user.is_superuser:
        return True
    return ROLE_ADMINISTRADOR in get_user_role_names(user)


def get_active_user_roles(user):
    return user.user_roles.select_related('role', 'organization').filter(ativo=True)


def get_accessible_organization_ids(user):
    if is_admin_sistema(user):
        orgs = Organization.objects.filter(is_active=True).select_related('parent')
        return [org.id for org in orgs if is_organization_contract_active(org)]

    org_ids = set()
    for user_role in get_active_user_roles(user):
        role_name = user_role.role.nome.upper()
        if role_name == ROLE_SECRETARIO_CAMPO and user_role.organization_id:
            org_ids.update(get_org_descendant_ids(user_role.organization))
        elif role_name in (ROLE_SECRETARIO_IGREJA, ROLE_PROFESSOR) and user_role.organization_id:
            org_ids.add(user_role.organization_id)

    if not org_ids:
        return []

    orgs = Organization.objects.filter(id__in=org_ids, is_active=True).select_related('parent')
    return [org.id for org in orgs if is_organization_contract_active(org)]


def get_accessible_organizations(user):
    org_ids = get_accessible_organization_ids(user)
    if not org_ids:
        return []
    orgs = Organization.objects.filter(id__in=org_ids, is_active=True).select_related('parent').order_by('nome')
    return [org for org in orgs if is_organization_contract_active(org)]


def can_access_organization(user, org_id):
    if is_admin_sistema(user):
        org = Organization.objects.filter(id=org_id).select_related('parent').first()
        return bool(org and is_organization_contract_active(org))

    if org_id not in set(get_accessible_organization_ids(user)):
        return False
    org = Organization.objects.filter(id=org_id).select_related('parent').first()
    return bool(org and is_organization_contract_active(org))


def can_manage_igrejas(user, active_org):
    if not is_campo_organization(active_org):
        return False
    if is_admin_sistema(user):
        return True
    role_names = get_user_role_names(user)
    if ROLE_SECRETARIO_CAMPO not in role_names:
        return False
    for user_role in get_active_user_roles(user):
        if user_role.role.nome.upper() != ROLE_SECRETARIO_CAMPO:
            continue
        if not user_role.organization_id:
            continue
        if active_org.id in get_org_descendant_ids(user_role.organization):
            return True
    return False


def get_roles_for_active_org(user, active_org):
    if is_admin_sistema(user):
        admin_role = (
            UserRole.objects.filter(user=user, ativo=True, role__nome=ROLE_ADMINISTRADOR)
            .select_related('role', 'organization')
            .first()
        )
        if admin_role:
            return [admin_role]
        return list(get_active_user_roles(user))

    active_org_id = active_org.id
    applicable = []
    for user_role in get_active_user_roles(user):
        role_name = user_role.role.nome.upper()
        if role_name == ROLE_SECRETARIO_CAMPO and user_role.organization_id:
            allowed_ids = get_org_descendant_ids(user_role.organization)
            if active_org_id in allowed_ids:
                applicable.append(user_role)
        elif role_name in (ROLE_SECRETARIO_IGREJA, ROLE_PROFESSOR):
            if user_role.organization_id == active_org_id:
                applicable.append(user_role)
    return applicable


def user_is_professor(user, organization=None):
    roles = get_active_user_roles(user).filter(role__nome=ROLE_PROFESSOR)
    if organization is not None:
        roles = roles.filter(organization=organization)
    return roles.exists()


def is_somente_professor(user, organization):
    if is_admin_sistema(user):
        return False
    role_names = {user_role.role.nome for user_role in get_roles_for_active_org(user, organization)}
    return ROLE_PROFESSOR in role_names and not role_names.intersection(FULL_OPERATIONAL_ROLES)


def get_teaching_class_ids(user, organization):
    from classrooms.models import ClassTeacher

    return list(
        ClassTeacher.objects.filter(
            user=user,
            class_group__organization=organization,
            class_group__is_active=True,
        ).values_list('class_group_id', flat=True)
    )


def get_effective_permissions(user, active_org):
    from access_control.models import ModulePermission

    permissions = {}
    for user_role in get_roles_for_active_org(user, active_org):
        for role_permission in user_role.role.permissions.select_related('permission').all():
            perm = role_permission.permission
            current = permissions.setdefault(
                perm.modulo,
                {
                    'visualizar': False,
                    'criar': False,
                    'editar': False,
                    'excluir': False,
                    'aprovar': False,
                },
            )
            for action in ('visualizar', 'criar', 'editar', 'excluir', 'aprovar'):
                current[action] = current[action] or getattr(perm, action, False)

    if active_org and is_somente_professor(user, active_org):
        turmas = permissions.get('turmas')
        if turmas:
            turmas['criar'] = False
            turmas['editar'] = False
            turmas['excluir'] = False
            turmas['aprovar'] = False
        usuarios = permissions.get('usuarios')
        if usuarios:
            for action in ('visualizar', 'criar', 'editar', 'excluir', 'aprovar'):
                usuarios[action] = False

    if is_admin_sistema(user):
        for module_perm in ModulePermission.objects.all():
            permissions[module_perm.modulo] = {
                'visualizar': True,
                'criar': True,
                'editar': True,
                'excluir': True,
                'aprovar': True,
            }

    return permissions


def requires_operational_context(org):
    return not is_operational_organization(org)


def user_requires_context_selection(user):
    if is_admin_sistema(user):
        return True
    role_names = get_user_role_names(user)
    return ROLE_SECRETARIO_CAMPO in role_names
