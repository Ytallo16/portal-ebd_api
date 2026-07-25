from organizations.models import Organization

from core.scoping import get_org_descendant_ids, is_campo_organization
from notifications.constants import (
    KIND_ATTENDANCE_PENDING,
    KIND_LESSON_FINALIZE,
    KIND_LESSON_TODAY,
    KIND_MAGAZINE_PAYMENT,
)
from notifications.services import collect_desired_notifications


ACTION_KINDS = {
    KIND_ATTENDANCE_PENDING,
    KIND_LESSON_FINALIZE,
    KIND_LESSON_TODAY,
    KIND_MAGAZINE_PAYMENT,
}


def _organizations_for_context(active_org):
    if not is_campo_organization(active_org):
        return [active_org]

    descendant_ids = get_org_descendant_ids(active_org, include_self=False)
    return list(
        Organization.objects.filter(
            id__in=descendant_ids,
            is_active=True,
        ).order_by('nome')
    )


def build_dashboard_actions(user, active_org):
    results = []
    organizations = _organizations_for_context(active_org)

    for organization in organizations:
        desired = collect_desired_notifications(user, organization)
        for item in desired:
            if item.kind not in ACTION_KINDS:
                continue
            results.append(
                {
                    'id': f'{organization.id}:{item.dedupe_key}',
                    'kind': item.kind,
                    'title': item.title,
                    'body': item.body,
                    'action_path': item.action_path,
                    'severity': item.severity,
                    'organization_id': organization.id,
                    'organization_name': organization.nome,
                    'metadata': item.metadata,
                }
            )

    results.sort(
        key=lambda item: (
            item['severity'] != 'WARNING',
            item['organization_name'].casefold(),
            item['title'].casefold(),
        )
    )

    summary_by_organization = []
    for organization in organizations:
        organization_items = [
            item for item in results if item['organization_id'] == organization.id
        ]
        summary_by_organization.append(
            {
                'organization_id': organization.id,
                'organization_name': organization.nome,
                'pending_count': len(organization_items),
                'warning_count': sum(
                    item['severity'] == 'WARNING' for item in organization_items
                ),
            }
        )

    return {
        'results': results,
        'total': len(results),
        'summary_by_organization': summary_by_organization,
    }
