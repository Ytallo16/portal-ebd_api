from organizations.models import OrganizationMembership


ORG_HEADER = 'HTTP_X_ORGANIZATION_ID'


def get_user_organization(request):
    user = request.user
    if not user or not user.is_authenticated:
        return None

    org_id = request.META.get(ORG_HEADER) or request.query_params.get('organization_id')
    memberships = OrganizationMembership.objects.filter(user=user, ativo=True).select_related('organization')

    if org_id:
        membership = memberships.filter(organization_id=org_id).first()
        # If the client sends a stale organization id, gracefully fallback to
        # any active membership instead of returning an empty tenant context.
        if membership:
            return membership.organization

    membership = memberships.first()
    return membership.organization if membership else None
