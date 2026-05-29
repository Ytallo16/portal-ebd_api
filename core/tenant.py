from rest_framework.exceptions import ValidationError

from core.scoping import can_access_organization, get_accessible_organizations, is_campo_organization
from organizations.models import Organization

ORG_HEADER = 'HTTP_X_ORGANIZATION_ID'


def _parse_org_id(raw_value):
    if raw_value in (None, ''):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        raise ValidationError({'detail': 'ID de organização inválido.'})


def resolve_active_organization(request, required=True):
    user = request.user
    if not user or not user.is_authenticated:
        return None

    org_id = _parse_org_id(request.META.get(ORG_HEADER) or request.query_params.get('organization_id'))
    if org_id is None and getattr(user, 'active_organization_id', None):
        org_id = user.active_organization_id

    if org_id is None:
        accessible = list(get_accessible_organizations(user))
        if len(accessible) == 1:
            org_id = accessible[0].id
        elif required:
            raise ValidationError({'detail': 'Contexto organizacional obrigatório (X-Organization-Id).'})
        else:
            return None

    if not can_access_organization(user, org_id):
        raise ValidationError({'detail': 'Organização fora do escopo do usuário.'})

    org = Organization.objects.filter(id=org_id, is_active=True).select_related('parent').first()
    if not org:
        raise ValidationError({'detail': 'Organização não encontrada.'})
    return org


def get_user_organization(request):
    return resolve_active_organization(request, required=True)


def get_operational_organization(request):
    org = resolve_active_organization(request, required=True)
    if is_campo_organization(org):
        raise ValidationError({'detail': 'Selecione uma igreja para esta operação.'})
    return org
